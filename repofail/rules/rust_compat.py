"""Rules: Rust version mismatch and platform-specific targets."""

import re

from ..models import HostProfile, RepoProfile
from .base import RuleResult, Severity


def _parse_rust_ver(s: str | None) -> tuple[int, int] | None:
    if not s:
        return None
    m = re.search(r"(\d+)\.(\d+)", s)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


def check_rust_version(repo: RepoProfile, host: HostProfile) -> RuleResult | None:
    """Check if host rustc is older than Cargo.toml rust-version."""
    if not repo.rust_version_req or not host.rust_version:
        return None
    req = _parse_rust_ver(repo.rust_version_req)
    host_ver = _parse_rust_ver(host.rust_version)
    if not req or not host_ver:
        return None
    if host_ver < req:
        return RuleResult(
            rule_id="rust_version_mismatch",
            severity=Severity.HIGH,
            message="Rust toolchain too old for this crate.",
            reason=f"Cargo.toml requires rust-version {repo.rust_version_req}, host has {host.rust_version}.",
            host_summary=f"rustc {host.rust_version}",
            evidence={"rust_version_req": repo.rust_version_req, "host_rust": host.rust_version},
            category="spec_violation",
            confidence="high",
        )
    return None


def check_rust_target_platform(repo: RepoProfile, host: HostProfile) -> RuleResult | None:
    """Check if Cargo.toml has target-specific deps that suggest a platform requirement."""
    if not repo.rust_target_platforms:
        return None
    host_os_map = {"macos": "macos", "linux": "linux", "windows": "windows"}
    host_os = host_os_map.get(host.os, host.os)
    # Check if ALL targets are for a different OS
    os_keywords = {"windows", "linux", "macos", "unix"}
    target_os_hints = set()
    for t in repo.rust_target_platforms:
        t_lower = t.lower()
        for kw in os_keywords:
            if kw in t_lower:
                target_os_hints.add(kw)
    # "unix" covers linux + macos
    if "unix" in target_os_hints:
        target_os_hints.update({"linux", "macos"})
    if target_os_hints and host_os not in target_os_hints:
        return RuleResult(
            rule_id="rust_target_platform",
            severity=Severity.MEDIUM,
            message="Rust crate has platform-specific targets that may not include this host.",
            reason=f"Target platforms: {', '.join(repo.rust_target_platforms[:5])}. Host: {host.os} {host.arch}.",
            host_summary=f"{host.os} {host.arch}",
            evidence={"targets": repo.rust_target_platforms, "host_os": host.os},
            category="architecture_mismatch",
            confidence="medium",
        )
    return None
