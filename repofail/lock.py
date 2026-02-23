"""Runtime lock — pin host + optional docker base for CI enforcement."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import __version__
from .scanner import inspect_host, scan_repo


LOCK_FILENAME = "repofail.lock.json"


def generate_lock(repo_path: Path) -> dict[str, Any]:
    """Build lock dict from current host and repo (docker base if present)."""
    host = inspect_host()
    lock: dict[str, Any] = {
        "repofail_lock": "1",
        "generated_by": f"repofail {__version__}",
        "python": host.python_version,
        "node": host.node_version,
        "cuda": host.cuda_version if host.cuda_available else None,
        "arch": host.arch,
        "os": host.os,
        "docker_base": None,
    }
    try:
        repo = scan_repo(repo_path)
        if repo.raw.get("dockerfile"):
            # First Dockerfile parsed may have base_image
            df = repo.raw["dockerfile"]
            if isinstance(df, dict) and df.get("base_image"):
                lock["docker_base"] = df["base_image"]
        # Also check first Dockerfile on disk if not in merged raw
        if lock["docker_base"] is None and repo.has_dockerfile:
            for p in (repo_path / "Dockerfile",):
                if p.exists():
                    from .scanner.parsers import parse_dockerfile
                    data = parse_dockerfile(p)
                    if data.get("base_image"):
                        lock["docker_base"] = data["base_image"]
                        break
    except Exception:
        pass
    return lock


def verify_lock(lock_path: Path) -> list[tuple[str, str, str]]:
    """
    Compare current host to lock. Returns list of (field, expected, actual) for mismatches.
    """
    if not lock_path.exists():
        return [("_lock", "file exists", str(lock_path) + " not found")]
    data = json.loads(lock_path.read_text())
    host = inspect_host()

    failures: list[tuple[str, str, str]] = []

    def _cmp(field: str, expected: Any, actual: Any) -> None:
        if expected is None:
            return
        if expected != actual:
            failures.append((field, str(expected), str(actual) if actual is not None else "missing"))

    _cmp("python", data.get("python"), host.python_version)
    _cmp("node", data.get("node"), host.node_version)
    _cmp("arch", data.get("arch"), host.arch)
    _cmp("os", data.get("os"), host.os)

    if data.get("cuda") is not None:
        if not host.cuda_available:
            failures.append(("cuda", str(data.get("cuda")), "not available"))
        elif host.cuda_version and data.get("cuda") != host.cuda_version:
            failures.append(("cuda", str(data.get("cuda")), str(host.cuda_version)))

    return failures
