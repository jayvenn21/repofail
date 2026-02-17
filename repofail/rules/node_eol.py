"""Rule: Node engine specifies EOL version (14, 16) — security/compliance risk."""

import re

from ..models import HostProfile, RepoProfile
from .base import RuleResult, Severity

# Node 14 EOL Apr 2023, Node 16 EOL Sep 2023
NODE_EOL_MAJORS = {14, 16}


def _engines_require_eol(spec: str) -> int | None:
    """If engines.node requires an EOL major, return it. Else None."""
    if not spec:
        return None
    # Match patterns like "14", "14.x", "16", "16.x", ">=14", "14.0.0", "^14"
    for part in re.split(r"[, ]+", spec.strip()):
        part = part.strip()
        m = re.match(r"(>=|<=|>|<|~|\^)?\s*(\d+)(?:\.|\.\*|\.x)?", part)
        if m:
            major = int(m.group(2))
            if major in NODE_EOL_MAJORS:
                return major
    return None


def check(repo: RepoProfile, host: HostProfile) -> RuleResult | None:
    """If engines.node requires Node 14 or 16 (EOL), flag HIGH."""
    if not repo.node_engine_spec:
        return None
    eol_major = _engines_require_eol(repo.node_engine_spec)
    if not eol_major:
        return None

    return RuleResult(
        rule_id="node_eol",
        severity=Severity.HIGH,
        message=f"Node {eol_major} is EOL — engines.node requires deprecated runtime.",
        reason=(
            f"package.json engines.node specifies Node {eol_major}.x. "
            f"Node {eol_major} reached end-of-life. Security and compatibility risk."
        ),
        host_summary=host.node_version or "unknown",
        evidence={
            "engines_node": repo.node_engine_spec,
            "eol_major": eol_major,
        },
        category="spec_violation",
        confidence="high",
    )
