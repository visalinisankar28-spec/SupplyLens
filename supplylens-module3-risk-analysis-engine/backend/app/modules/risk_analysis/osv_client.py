"""
Async client for the OSV.dev vulnerability database API.

OSV.dev docs: https://osv.dev/docs/

We only use the two endpoints we actually need:
  - POST /v1/query        -> vulnerabilities affecting a specific package@version
  - POST /v1/querybatch    -> same, but batched (used for whole-application scans)

This client is intentionally thin: it does not interpret CVSS or severity,
that logic lives in service.py so it stays testable and swappable.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

OSV_BASE_URL = "https://api.osv.dev/v1"
DEFAULT_TIMEOUT = 15.0


class OSVClient:
    """Thin async wrapper around the OSV.dev REST API."""

    def __init__(self, base_url: str = OSV_BASE_URL, timeout: float = DEFAULT_TIMEOUT) -> None:
        self.base_url = base_url
        self.timeout = timeout

    async def query_package(
        self, package_name: str, ecosystem: str, version: str
    ) -> list[dict[str, Any]]:
        """
        Return the raw list of OSV vulnerability records affecting
        `package_name@version` in the given ecosystem (e.g. "PyPI", "npm", "Maven").
        """
        payload = {
            "package": {"name": package_name, "ecosystem": ecosystem},
            "version": version,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(f"{self.base_url}/query", json=payload)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning(
                    "OSV query failed for %s@%s (%s): %s", package_name, version, ecosystem, exc
                )
                return []
        return response.json().get("vulns", [])

    async def query_batch(
        self, packages: list[dict[str, str]]
    ) -> list[list[dict[str, Any]]]:
        """
        Batched version of query_package.

        `packages` is a list of {"name": ..., "ecosystem": ..., "version": ...}.
        Returns a list of vuln-id-only results (OSV batch API returns IDs only;
        callers should follow up with `get_vulnerability` for full detail on
        anything new/uncached).
        """
        queries = [
            {
                "package": {"name": p["name"], "ecosystem": p["ecosystem"]},
                "version": p["version"],
            }
            for p in packages
        ]
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/querybatch", json={"queries": queries}
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning("OSV batch query failed for %d packages: %s", len(packages), exc)
                return [[] for _ in packages]
        results = response.json().get("results", [])
        return [r.get("vulns", []) for r in results]

    async def get_vulnerability(self, vuln_id: str) -> Optional[dict[str, Any]]:
        """Fetch full detail for a single vulnerability ID (used to hydrate batch results)."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(f"{self.base_url}/vulns/{vuln_id}")
                response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning("OSV detail fetch failed for %s: %s", vuln_id, exc)
                return None
        return response.json()
