"""Rule: requires-python pins to EOL version (3.7, 3.8) — security risk."""

import re

from ..models import HostProfile, RepoProfile
from .base import RuleResult, Severity

# Python 3.7 EOL Jun 2023, 3.8 EOL Oct 2024
PYTHON_EOL_MINORS = (3, 7), (3, 8)


def _requires_python_eol(spec: str) -> tuple[int, int] | None:
    """If requires-python pins to EOL (3.7 or 3.8), return (3, 7) or (3, 8). Else None."""
    if not spec:
        return None
    spec = spec.strip().lower()
    # Exact pins: ==3.7, ==3.8, ==3.7.*, ~=3.7, ~=3.8
    for (major, minor) in PYTHON_EOL_MINORS:
        if re.search(rf"(==|~=)\s*{major}\.{minor}(\.\*)?\b", spec):
            return (major, minor)
    # Range that allows only EOL: >=3.7,<3.9 (3.7 and 3.8 only)
    if re.search(r"3\.7|3\.8", spec) and re.search(r"<3\.9\b|<=3\.8\b", spec):
        if "3.10" not in spec and "3.11" not in spec and "3.12" not in spec:
            return (3, 8)  # most restrictive in range
    return None


def check(repo: RepoProfile, host: HostProfile) -> RuleResult | None:
    """If requires-python pins to Python 3.7 or 3.8 (EOL), flag HIGH."""
    if not repo.python_version:
        return None
    eol = _requires_python_eol(repo.python_version)
    if not eol:
        return None
    major, minor = eol

    return RuleResult(
        rule_id="python_eol",
        severity=Severity.HIGH,
        message=f"Python {major}.{minor} is EOL — requires-python pins to deprecated runtime.",
        reason=(
            f"requires-python allows/pins Python {major}.{minor}. "
            f"Python {major}.{minor} reached end-of-life. Security and compatibility risk."
        ),
        host_summary=f"Python {host.python_version or '?'}",
        evidence={
            "requires_python": repo.python_version,
            "eol_version": f"{major}.{minor}",
        },
        category="spec_violation",
        confidence="high",
    )
