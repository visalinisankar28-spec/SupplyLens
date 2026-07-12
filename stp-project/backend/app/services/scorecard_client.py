"""
OpenSSF Scorecard API client.

Design decision: we deliberately do NOT hand-roll our own repository-activity
heuristics against the raw GitHub API. The OpenSSF Scorecard project already
runs 18 standardized checks (including "Maintained" and "Contributors")
across 1M+ of the most-used open source projects and exposes the results via
a public, unauthenticated REST API. Re-implementing this would be wasted
engineering effort and a weaker, less credible signal than the industry
standard. This module's contribution is what happens *after* this data is
collected (aggregation, concentration analysis, DHI scoring) - not the
collection itself.

Reference: https://api.scorecard.dev
"""
import logging
from dataclasses import dataclass

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


@dataclass(frozen=True)
class ScorecardResult:
    """Normalized subset of a Scorecard response that the health engine needs."""

    overall_score: float | None
    maintained_check_score: float | None
    contributors_check_score: float | None
    raw_checks: dict


class ScorecardClient:
    """Thin, typed wrapper around the OpenSSF Scorecard public REST API."""

    def __init__(self, http_client: httpx.Client | None = None) -> None:
        # Allow dependency injection of the HTTP client so tests can supply
        # a mocked transport instead of hitting the network.
        self._client = http_client or httpx.Client(
            base_url=settings.scorecard_api_base_url,
            timeout=settings.external_api_timeout_seconds,
        )

    def get_scorecard(self, owner: str, repo: str) -> ScorecardResult | None:
        """
        Fetch the Scorecard result for a GitHub repository.

        Returns None (rather than raising) when the repo has never been
        scored or is unreachable - the health engine treats "unknown" as a
        distinct, honest state rather than silently defaulting to a score.
        """
        url = f"/projects/github.com/{owner}/{repo}"
        try:
            response = self._client.get(url)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                logger.info("No Scorecard result for %s/%s (not yet scored)", owner, repo)
            else:
                logger.warning("Scorecard API error for %s/%s: %s", owner, repo, exc)
            return None
        except httpx.HTTPError as exc:
            logger.warning("Scorecard API unreachable for %s/%s: %s", owner, repo, exc)
            return None

        payload = response.json()
        return self._parse_response(payload)

    @staticmethod
    def _parse_response(payload: dict) -> ScorecardResult:
        """Extract the specific checks the DHI algorithm consumes."""
        checks = {check["name"]: check["score"] for check in payload.get("checks", [])}
        return ScorecardResult(
            overall_score=payload.get("score"),
            maintained_check_score=checks.get("Maintained"),
            contributors_check_score=checks.get("Contributors"),
            raw_checks=checks,
        )

    def close(self) -> None:
        self._client.close()
