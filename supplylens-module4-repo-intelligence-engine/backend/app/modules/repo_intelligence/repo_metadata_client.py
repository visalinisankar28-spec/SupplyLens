"""
Async client for raw repository metadata (stars, forks, contributors,
commits, releases) via the GitHub REST API.

Only GitHub is implemented for the hackathon scope; GitLab/Bitbucket are
listed as future improvements (see README_MODULE4.md).
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 15.0


class RepoMetadataClient:
    def __init__(self, token: Optional[str] = None, timeout: float = DEFAULT_TIMEOUT) -> None:
        self.timeout = timeout
        self.headers = {"Accept": "application/vnd.github+json"}
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    async def get_repo_summary(self, owner: str, repo: str) -> dict[str, Any]:
        """Basic repo metadata: stars, forks, open issues."""
        url = f"https://api.github.com/repos/{owner}/{repo}"
        async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
            try:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPError as exc:
                logger.warning("GitHub repo summary fetch failed for %s/%s: %s", owner, repo, exc)
                return {}
        return {
            "stars": data.get("stargazers_count"),
            "forks": data.get("forks_count"),
            "open_issues": data.get("open_issues_count"),
            "pushed_at": data.get("pushed_at"),  # last commit to default branch, approx.
        }

    async def get_latest_release(self, owner: str, repo: str) -> Optional[datetime]:
        url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
        async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
            try:
                response = await client.get(url)
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPError as exc:
                logger.warning("GitHub release fetch failed for %s/%s: %s", owner, repo, exc)
                return None
        published_at = data.get("published_at")
        return _parse_iso(published_at) if published_at else None

    async def get_release_count_last_year(self, owner: str, repo: str) -> int:
        url = f"https://api.github.com/repos/{owner}/{repo}/releases"
        async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
            try:
                response = await client.get(url, params={"per_page": 100})
                response.raise_for_status()
                releases = response.json()
            except httpx.HTTPError as exc:
                logger.warning("GitHub releases list fetch failed for %s/%s: %s", owner, repo, exc)
                return 0

        one_year_ago = datetime.utcnow().timestamp() - (365 * 24 * 3600)
        count = 0
        for r in releases:
            published_at = r.get("published_at")
            if published_at and _parse_iso(published_at).timestamp() >= one_year_ago:
                count += 1
        return count

    async def get_contributor_commit_shares(self, owner: str, repo: str) -> list[dict[str, Any]]:
        """
        Returns [{"login": ..., "contributions": ...}, ...] sorted desc.
        Used to compute bus-factor / top-contributor concentration.
        """
        url = f"https://api.github.com/repos/{owner}/{repo}/contributors"
        async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
            try:
                response = await client.get(url, params={"per_page": 100})
                response.raise_for_status()
                contributors = response.json()
            except httpx.HTTPError as exc:
                logger.warning("GitHub contributors fetch failed for %s/%s: %s", owner, repo, exc)
                return []
        return [
            {"login": c.get("login"), "contributions": c.get("contributions", 0)}
            for c in contributors
            if isinstance(c, dict)
        ]


def _parse_iso(value: str) -> datetime:
    return datetime.strptime(value.replace("Z", "+0000"), "%Y-%m-%dT%H:%M:%S%z").replace(tzinfo=None)


def parse_repo_url(repo_url: str) -> tuple[str, str, str]:
    """
    Parse a repo URL into (host, owner, repo). Only handles GitHub HTTPS
    URLs for this module's scope, e.g. https://github.com/expressjs/express
    """
    cleaned = repo_url.rstrip("/").removesuffix(".git")
    parts = cleaned.split("/")
    if len(parts) < 2 or "github.com" not in cleaned:
        raise ValueError(f"Unsupported or unparseable repo URL: {repo_url}")
    owner, repo = parts[-2], parts[-1]
    return "github.com", owner, repo
