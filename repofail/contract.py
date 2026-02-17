"""Environment contract — versioned runtime expectations."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from . import __version__
from .models import RepoProfile


@dataclass
class EnvironmentContract:
    """Versioned runtime expectations for a repository."""

    repo: str = ""
    version: str = "1"
    requires: dict[str, Any] = field(default_factory=dict)
    optional: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "repofail_contract": self.version,
            "generated_by": f"repofail {__version__}",
            "repo": self.repo,
            "requires": self.requires,
            "optional": self.optional,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


def generate_contract(repo: RepoProfile) -> EnvironmentContract:
    """Build an environment contract from a RepoProfile."""
    requires: dict[str, Any] = {}
    optional: dict[str, Any] = {}

    if repo.python_version:
        requires["python"] = repo.python_version

    if repo.uses_torch or repo.uses_tensorflow:
        if repo.requires_cuda:
            requires["cuda"] = True
        else:
            optional["cuda"] = True

    has_native = bool(repo.node_native_modules or repo.has_cargo_toml or repo.rust_system_libs)
    if has_native:
        requires["compiler"] = True

    if repo.has_package_json:
        requires["node"] = True

    if repo.has_cargo_toml:
        requires["rust"] = True

    if repo.uses_torch and repo.frameworks and ("Diffusers" in repo.frameworks or "Transformers" in repo.frameworks):
        optional["ram_gb"] = 16

    return EnvironmentContract(
        repo=repo.name or repo.path,
        requires=requires,
        optional=optional,
    )


def validate_contract(contract: EnvironmentContract, host_data: dict) -> list[tuple[str, str]]:
    """
    Validate host against contract. Returns list of (requirement, reason) for failures.
    host_data: dict with python_version, cuda_available, has_compiler, has_node, has_rust, ram_gb
    """
    failures: list[tuple[str, str]] = []

    for key, value in contract.requires.items():
        if key == "python":
            host_py = host_data.get("python_version")
            if host_py and not _python_satisfies(host_py, str(value)):
                failures.append((key, f"Host Python {host_py} does not satisfy {value}"))
        elif key == "cuda" and value is True:
            if not host_data.get("cuda_available", False):
                failures.append((key, "CUDA required but not available"))
        elif key == "compiler" and value is True:
            if not host_data.get("has_compiler", False):
                failures.append((key, "Compiler required for native builds"))
        elif key == "node" and value is True:
            if not host_data.get("node_version"):
                failures.append((key, "Node required but not found"))
        elif key == "rust" and value is True:
            if not host_data.get("rust_version"):
                failures.append((key, "Rust required but not found"))

    return failures


def _python_satisfies(version: str, spec: str) -> bool:
    """Simple check: version satisfies requires-python spec."""
    import re
    try:
        v = tuple(int(x) for x in version.split(".")[:3])
    except (ValueError, TypeError):
        return True
    for part in re.split(r"[, ]+", spec):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"(>=|<=|>|<)\s*(\d+)\.(\d+)(?:\.(\d+))?", part)
        if not m:
            continue
        op, ma, mi, pa = m.groups()
        other = (int(ma), int(mi), int(pa) if pa else 0)
        if op == ">=" and v < other:
            return False
        if op == "<=" and v > other:
            return False
        if op == ">" and v <= other:
            return False
        if op == "<" and v >= other:
            return False
    return True
