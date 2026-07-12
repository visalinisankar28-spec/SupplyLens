"""
Package registry metadata client.

Scorecard tells us how a repository behaves. It does not tell us, on its
own, when a package was last *released* to its registry - a distinct and
important signal (a repo can look active on GitHub while its published
package has not shipped in years, e.g. maintenance happening on an
unreleased branch). This client fills that gap using each ecosystem's
public, unauthenticated registry API.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


@dataclass(frozen=True)
class RegistryMetadata:
    """Normalized registry metadata, regardless of source ecosystem."""

    repository_url: str | None
    last_release_at: datetime | None


class RegistryClient:
    """Queries npm, PyPI, or Maven Central depending on the component's ecosystem."""

    def __init__(self, http_client: httpx.Client | None = None) -> None:
        self._client = http_client or httpx.Client(
            timeout=settings.external_api_timeout_seconds
        )

    def get_metadata(self, ecosystem: str, package_name: str) -> RegistryMetadata | None:
        """Dispatch to the correct ecosystem-specific fetcher."""
        fetchers = {
            "npm": self._fetch_npm,
            "pypi": self._fetch_pypi,
            "maven": self._fetch_maven,
        }
        fetcher = fetchers.get(ecosystem.lower())
        if fetcher is None:
            logger.info("Unsupported ecosystem '%s' - skipping registry lookup", ecosystem)
            return None
        try:
            return fetcher(package_name)
        except httpx.HTTPError as exc:
            logger.warning("Registry lookup failed for %s/%s: %s", ecosystem, package_name, exc)
            return None

    def _fetch_npm(self, package_name: str) -> RegistryMetadata | None:
        url = f"{settings.npm_registry_base_url}/{package_name}"
        response = self._client.get(url)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        payload = response.json()

        repo_field = payload.get("repository")
        repo_url = None
        if isinstance(repo_field, dict):
            repo_url = repo_field.get("url")
        elif isinstance(repo_field, str):
            repo_url = repo_field

        latest_version = payload.get("dist-tags", {}).get("latest")
        release_time_str = payload.get("time", {}).get(latest_version) if latest_version else None
        last_release_at = _parse_iso8601(release_time_str)

        return RegistryMetadata(repository_url=_clean_repo_url(repo_url), last_release_at=last_release_at)

    def _fetch_pypi(self, package_name: str) -> RegistryMetadata | None:
        url = f"{settings.pypi_registry_base_url}/{package_name}/json"
        response = self._client.get(url)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        payload = response.json()

        info = payload.get("info", {})
        project_urls = info.get("project_urls") or {}
        repo_url = (
            project_urls.get("Source")
            or project_urls.get("Repository")
            or project_urls.get("Homepage")
            or info.get("home_page")
        )

        releases = payload.get("releases", {})
        latest_version = info.get("version")
        release_files = releases.get(latest_version, []) if latest_version else []
        last_release_at = None
        if release_files:
            upload_times = [f.get("upload_time_iso_8601") for f in release_files if f.get("upload_time_iso_8601")]
            if upload_times:
                last_release_at = _parse_iso8601(max(upload_times))

        return RegistryMetadata(repository_url=_clean_repo_url(repo_url), last_release_at=last_release_at)

    def _fetch_maven(self, package_name: str) -> RegistryMetadata | None:
        """
        Best-effort Maven Central lookup.

        NOTE: Maven Central's search API does not reliably expose an SCM/
        repository URL the way npm and PyPI do (it requires parsing the
        artifact's POM file separately). This is a known, documented
        limitation for the MVP - see README "Future Improvements".
        """
        response = self._client.get(
            settings.maven_search_base_url,
            params={"q": f"a:{package_name}", "core": "gav", "rows": "1", "wt": "json"},
        )
        response.raise_for_status()
        docs = response.json().get("response", {}).get("docs", [])
        if not docs:
            return None
        timestamp_ms = docs[0].get("timestamp")
        last_release_at = (
            datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc) if timestamp_ms else None
        )
        # Repository URL resolution intentionally left as a future improvement.
        return RegistryMetadata(repository_url=None, last_release_at=last_release_at)

    def close(self) -> None:
        self._client.close()


def _parse_iso8601(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _clean_repo_url(raw_url: str | None) -> str | None:
    """Normalize common repository URL formats (git+https, .git suffix, ssh)."""
    if not raw_url:
        return None
    url = raw_url.strip()
    url = url.removeprefix("git+")
    url = url.removesuffix(".git")
    url = url.replace("git://", "https://").replace("ssh://git@", "https://")
    return url
