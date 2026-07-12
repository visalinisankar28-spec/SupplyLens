"""
License compatibility rule engine.

Deliberately a static, auditable table rather than a model — the whole
point of SupplyLens's Enterprise Risk Score is that every number must be
traceable to a rule a human can read. This module is the license half of
that contract.

SPDX identifiers: https://spdx.org/licenses/
"""
from __future__ import annotations

from enum import Enum


class LicensePolicyStatus(str, Enum):
    ALLOWED = "ALLOWED"
    REVIEW = "REVIEW"
    DENIED = "DENIED"
    UNKNOWN = "UNKNOWN"


# Permissive licenses safe for use in a proprietary/commercial product.
_ALLOWED: set[str] = {
    "MIT",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "ISC",
    "0BSD",
    "Unlicense",
    "Python-2.0",
    "Zlib",
}

# Weak/partial copyleft — safe in many architectures (e.g. dynamic linking)
# but needs a human to confirm how the package is actually used.
_REVIEW: set[str] = {
    "LGPL-2.1",
    "LGPL-2.1-only",
    "LGPL-2.1-or-later",
    "LGPL-3.0",
    "LGPL-3.0-only",
    "LGPL-3.0-or-later",
    "MPL-2.0",
    "EPL-2.0",
    "CDDL-1.0",
}

# Strong copyleft — generally incompatible with a closed-source product
# unless the org has an explicit exception.
_DENIED: set[str] = {
    "GPL-2.0",
    "GPL-2.0-only",
    "GPL-2.0-or-later",
    "GPL-3.0",
    "GPL-3.0-only",
    "GPL-3.0-or-later",
    "AGPL-3.0",
    "AGPL-3.0-only",
    "AGPL-3.0-or-later",
    "SSPL-1.0",
}

# Score bands used by service.py to build license_risk_score.
SCORE_BY_STATUS: dict[LicensePolicyStatus, float] = {
    LicensePolicyStatus.ALLOWED: 0.0,
    LicensePolicyStatus.REVIEW: 5.0,
    LicensePolicyStatus.DENIED: 10.0,
    LicensePolicyStatus.UNKNOWN: 6.0,  # treated conservatively - unknown is not "safe"
}


def classify_license(spdx_id: str | None) -> LicensePolicyStatus:
    """Classify a single SPDX license identifier against the org policy."""
    if not spdx_id:
        return LicensePolicyStatus.UNKNOWN

    normalized = spdx_id.strip()

    if normalized in _ALLOWED:
        return LicensePolicyStatus.ALLOWED
    if normalized in _REVIEW:
        return LicensePolicyStatus.REVIEW
    if normalized in _DENIED:
        return LicensePolicyStatus.DENIED
    return LicensePolicyStatus.UNKNOWN


def license_risk_score(spdx_id: str | None) -> tuple[float, LicensePolicyStatus, str]:
    """
    Returns (score, status, human_readable_reason) for a given license.
    This tuple is what gets written into PackageRiskProfile.explanation.
    """
    status = classify_license(spdx_id)
    score = SCORE_BY_STATUS[status]

    reasons = {
        LicensePolicyStatus.ALLOWED: f"'{spdx_id}' is a permissive license, no restriction on commercial use.",
        LicensePolicyStatus.REVIEW: f"'{spdx_id}' is weak-copyleft; safe in most architectures but flagged for manual review.",
        LicensePolicyStatus.DENIED: f"'{spdx_id}' is strong-copyleft and conflicts with closed-source distribution policy.",
        LicensePolicyStatus.UNKNOWN: "No recognized SPDX license identifier found; treated as high risk until confirmed.",
    }
    return score, status, reasons[status]
