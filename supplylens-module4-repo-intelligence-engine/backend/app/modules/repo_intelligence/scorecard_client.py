"""
Async client for the OpenSSF Scorecard REST API.

Docs: https://api.securityscorecards.dev
Public deployment serves precomputed scores for repos already scanned by
the OpenSSF batch job; not every repo will have a cached result, in which
case we degrade gracefully (score = None) rather than failing the scan.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 15.0


class ScorecardClient:
    def __init__(
        self,
        base_url: str = "https://api.securityscorecards.dev",
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = base_url
        self.timeout = timeout

    async def get_scorecard(self, repo_host: str, repo_path: str) -> Optional[dict[str, Any]]:
        """
        Fetch the Scorecard result for a repo, e.g.
        repo_host="github.com", repo_path="expressjs/express".

        Returns None if no Scorecard result exists yet for this repo
        (common for smaller/newer projects) -- callers must handle this by
        falling back to maintenance/activity/bus-factor signals only.
        """
        url = f"{self.base_url}/projects/{repo_host}/{repo_path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url)
                if response.status_code == 404:
                    logger.info("No Scorecard result cached for %s/%s", repo_host, repo_path)
                    return None
                response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning("Scorecard fetch failed for %s/%s: %s", repo_host, repo_path, exc)
                return None
        return response.json()

    @staticmethod
    def extract_overall_score(scorecard_payload: dict[str, Any]) -> Optional[float]:
        score = scorecard_payload.get("score")
        return float(score) if score is not None else None

    @staticmethod
    def extract_checks(scorecard_payload: dict[str, Any]) -> dict[str, Any]:
        """Flatten the checks list into {check_name: {score, reason}} for storage/audit."""
        checks = {}
        for check in scorecard_payload.get("checks", []):
            checks[check.get("name", "unknown")] = {
                "score": check.get("score"),
                "reason": check.get("reason"),
            }
        return checks
