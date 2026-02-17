"""Rule: Missing system libs (libGL, ffmpeg)."""

from ..models import HostProfile, RepoProfile
from .base import RuleResult, Severity


def check(repo: RepoProfile, host: HostProfile) -> RuleResult | None:
    """Repo requires libGL or ffmpeg but host doesn't have it."""
    reasons = []
    if repo.requires_libgl and not host.has_libgl:
        reasons.append("libGL (opencv, PyOpenGL)")
    if repo.requires_ffmpeg and not host.has_ffmpeg:
        reasons.append("ffmpeg")
    if not reasons:
        return None

    return RuleResult(
        rule_id="missing_system_libs",
        severity=Severity.MEDIUM,
        message="Repo requires system libraries that are not detected.",
        reason="; ".join(reasons),
        host_summary=f"{host.os} {host.arch}",
        category="toolchain_missing",
    )
