"""Rule: Node native bindings on Windows."""

from ..models import HostProfile, RepoProfile
from .base import RuleResult, Severity


def check(repo: RepoProfile, host: HostProfile) -> RuleResult | None:
    """Node native modules (node-gyp) often problematic on Windows."""
    if host.os != "windows":
        return None
    if not repo.node_native_modules:
        return None

    return RuleResult(
        rule_id="node_native_windows",
        severity=Severity.MEDIUM,
        message="Node native modules often fail to build on Windows.",
        reason=f"Packages: {', '.join(repo.node_native_modules[:3])}",
        host_summary="Windows",
        category="toolchain_missing",
    )
