"""Rule: Node engine version violation — package.json engines.node vs host."""

import re

from ..models import HostProfile, RepoProfile
from .base import RuleResult, Severity


def _parse_node_version(s: str | None) -> tuple[int, int] | None:
    """Parse node version string to (major, minor). 'v20.12.2' -> (20, 12)."""
    if not s:
        return None
    m = re.search(r"(\d+)\.(\d+)", str(s))
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


def _node_in_range(version: tuple[int, int], spec: str) -> bool:
    """Check if (major, minor) satisfies engines spec like '>=18', '18.x', '^18.0.0'."""
    for part in re.split(r"[, ]+", spec.strip()):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"(>=|<=|>|<|~|\^)?\s*(\d+)(?:\.(\d+))?(?:\.\*|\.x)?", part)
        if not m:
            continue
        op, ma, mi = m.group(1), int(m.group(2)), int(m.group(3) or 0)
        other = (ma, mi)
        if op is None:  # "18" or "18.x" = must match major
            if version[0] != ma:
                return False
            continue
        if op == ">=" and version < other:
            return False
        if op == "<=" and version > other:
            return False
        if op == ">" and version <= other:
            return False
        if op == "<" and version >= other:
            return False
        if op in ("~", "^"):  # tilde/caret: same major, min minor
            if version[0] != ma:
                return False
            if version[1] < mi:
                return False
    return True


def check(repo: RepoProfile, host: HostProfile) -> RuleResult | None:
    """If package.json engines.node is set and host Node is outside range, flag HIGH."""
    if not repo.node_engine_spec or not host.node_version:
        return None

    host_ver = _parse_node_version(host.node_version)
    if not host_ver:
        return None

    if _node_in_range(host_ver, repo.node_engine_spec):
        return None

    return RuleResult(
        rule_id="node_engine_mismatch",
        severity=Severity.HIGH,
        message="Node engine constraint violated.",
        reason=(
            f"engines.node: {repo.node_engine_spec}, host: {host.node_version}. "
            "npm/yarn may refuse to install or runtime may fail."
        ),
        host_summary=f"Node {host.node_version}",
        evidence={
            "engines_node": repo.node_engine_spec,
            "host_node": host.node_version,
            "determinism": 1.0,
            "breakage_likelihood": "~100%",
            "likely_error": "npm ERR! code EBADENGINE / runtime version mismatch",
        },
        category="spec_violation",
        confidence="high",
    )
