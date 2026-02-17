"""Rule 4: Native build toolchain missing."""

from ..models import HostProfile, RepoProfile
from .base import RuleResult, Severity


def check(repo: RepoProfile, host: HostProfile) -> RuleResult | None:
    """If repo has native modules and host missing compiler/Rust, flag HIGH for Cargo/maturin, MEDIUM otherwise."""
    native_backends = repo.raw.get("native_build_backends", [])
    has_native = (
        bool(repo.node_native_modules)
        or bool(repo.rust_system_libs)
        or repo.has_cargo_toml
        or bool(native_backends)
    )
    if not has_native:
        return None

    # Cargo/Rust/maturin need Rust; node/setup.py need compiler
    needs_rust = repo.has_cargo_toml or "maturin" in native_backends or "setuptools-rust" in native_backends
    if needs_rust and host.rust_version:
        return None
    if not needs_rust and host.has_compiler:
        return None
    severity = Severity.HIGH if needs_rust else Severity.MEDIUM

    reasons = []
    if repo.node_native_modules:
        reasons.append(f"Node native: {', '.join(repo.node_native_modules[:3])}")
    if repo.has_cargo_toml or repo.rust_system_libs:
        reasons.append("Cargo.toml / Rust")
    if native_backends:
        reasons.append(f"Build backends: {', '.join(native_backends)}")
    if repo.has_setup_py:
        reasons.append("setup.py with C extensions")

    evidence = {
        "has_cargo": repo.has_cargo_toml,
        "native_build_backends": native_backends,
        "host_has_compiler": host.has_compiler,
        "host_rust": bool(host.rust_version),
    }

    return RuleResult(
        rule_id="native_toolchain_missing",
        severity=severity,
        message="Native extension detected but required toolchain missing.",
        reason="; ".join(reasons) + ". Build will fail during installation."
        if reasons else "node-gyp, Rust, or C extension build required.",
        host_summary=f"{host.os} {host.arch}",
        evidence=evidence,
        category="toolchain_missing",
    )
