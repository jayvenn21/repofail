"""Rule: package.json has dependencies but no lock file — npm ci will fail."""

from ..models import HostProfile, RepoProfile
from .base import RuleResult, Severity


def check(repo: RepoProfile, host: HostProfile) -> RuleResult | None:
    """If package.json has deps and no package-lock.json or yarn.lock, flag HIGH."""
    if not repo.has_package_json or not repo.node_lock_file_missing:
        return None

    return RuleResult(
        rule_id="lock_file_missing",
        severity=Severity.HIGH,
        message="No lock file (package-lock.json or yarn.lock) — npm ci will fail.",
        reason=(
            "package.json has dependencies but no package-lock.json or yarn.lock. "
            "npm ci requires a lock file. npm install will produce non-deterministic installs."
        ),
        host_summary=host.os or "unknown",
        evidence={
            "has_deps": True,
            "lock_files": "none",
            "expected_failure": "npm ci fails; npm install non-deterministic",
        },
        category="spec_violation",
        confidence="high",
    )
