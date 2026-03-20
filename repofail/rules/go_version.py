"""Rule: Go version mismatch - go.mod go directive vs host Go."""

import re

from ..models import HostProfile, RepoProfile
from .base import RuleResult, Severity


def _parse_go_ver(s: str | None) -> tuple[int, int] | None:
    if not s:
        return None
    m = re.search(r"(\d+)\.(\d+)", s)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


def check(repo: RepoProfile, host: HostProfile) -> RuleResult | None:
    if not repo.go_version or not host.go_version:
        return None
    repo_ver = _parse_go_ver(repo.go_version)
    host_ver = _parse_go_ver(host.go_version)
    if not repo_ver or not host_ver:
        return None
    if host_ver < repo_ver:
        return RuleResult(
            rule_id="go_version_mismatch",
            severity=Severity.HIGH,
            message="Go version too old for this module.",
            reason=f"go.mod requires go {repo.go_version}, host has {host.go_version}. Build will fail.",
            host_summary=f"Go {host.go_version}",
            evidence={"go_mod_version": repo.go_version, "host_go": host.go_version},
            category="spec_violation",
            confidence="high",
        )
    return None


def check_cgo(repo: RepoProfile, host: HostProfile) -> RuleResult | None:
    if not repo.go_cgo_deps:
        return None
    if not host.has_compiler:
        return RuleResult(
            rule_id="go_cgo_no_compiler",
            severity=Severity.MEDIUM,
            message="Go project uses CGO but no C compiler found.",
            reason=f"CGO deps: {', '.join(repo.go_cgo_deps[:5])}. Build requires gcc/clang.",
            host_summary=f"{host.os} {host.arch}, no compiler",
            evidence={"cgo_deps": repo.go_cgo_deps},
            category="toolchain_missing",
            confidence="high",
        )
    return None


def check_os_build_tags(repo: RepoProfile, host: HostProfile) -> RuleResult | None:
    if not repo.go_os_specific_tags:
        return None
    host_os_map = {"macos": "darwin", "linux": "linux", "windows": "windows"}
    host_os = host_os_map.get(host.os, host.os)
    if host_os not in repo.go_os_specific_tags and len(repo.go_os_specific_tags) > 0:
        all_non_host = all(t != host_os for t in repo.go_os_specific_tags)
        if all_non_host:
            return RuleResult(
                rule_id="go_os_build_tags",
                severity=Severity.MEDIUM,
                message="Go project has OS-specific build tags that exclude this host.",
                reason=f"Build tags target: {', '.join(repo.go_os_specific_tags)}. Host: {host.os}.",
                host_summary=f"{host.os} {host.arch}",
                evidence={"build_tags": repo.go_os_specific_tags, "host_os": host.os},
                category="architecture_mismatch",
                confidence="medium",
            )
    return None
