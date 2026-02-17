"""Rule 3: Python version constraint violation."""

import re

from ..models import HostProfile, RepoProfile
from .base import RuleResult, Severity


def _parse_version(s: str) -> tuple[int, int, int]:
    """Parse '3.11.2' -> (3, 11, 2)."""
    parts = s.split(".")[:3]
    return tuple(int(p) for p in parts if p.isdigit())


def _version_in_range(version: str, spec: str) -> bool:
    """
    Check if version satisfies requires-python spec.
    Supports: >=3.10, <3.12, ~=3.10, ==3.11.*
    """
    try:
        v = _parse_version(version)
    except (ValueError, TypeError):
        return True  # Can't parse, assume OK

    # Simple patterns: >=3.10, <3.12, >3.9, <=3.11
    for part in re.split(r"[, ]+", spec):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"(>=|<=|>|<|==|!=|~=)\s*(\d+)\.(\d+)(?:\.(\d+))?", part)
        if not m:
            continue
        op, ma, mi, pa = m.groups()
        ma, mi = int(ma), int(mi)
        pa = int(pa) if pa else 0
        other = (ma, mi, pa)

        if op == ">=" and v < other:
            return False
        if op == "<=" and v > other:
            return False
        if op == ">" and v <= other:
            return False
        if op == "<" and v >= other:
            return False
        if op == "==":
            if "." in part and ".*" in part:
                if v[0] != other[0] or v[1] != other[1]:
                    return False
            elif v != other:
                return False
    return True


def check(repo: RepoProfile, host: HostProfile) -> RuleResult | None:
    """If requires-python exists and host version outside range, flag HIGH."""
    if not repo.python_version or not host.python_version:
        return None

    if _version_in_range(host.python_version, repo.python_version):
        return None

    return RuleResult(
        rule_id="python_version_mismatch",
        severity=Severity.HIGH,
        message="Host Python version violates repository requirement.",
        reason=(
            f"Repo requires {repo.python_version}, host has {host.python_version}. "
            "This environment is outside the declared compatibility range. "
            "Installation may succeed but runtime behavior is undefined."
        ),
        host_summary=f"{host.os} {host.arch}, Python {host.python_version}",
        evidence={"requires_python": repo.python_version, "host_python": host.python_version},
        category="spec_violation",
    )
