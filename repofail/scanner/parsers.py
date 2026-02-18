"""Parsers for dependency and config files."""

import json
import re
from pathlib import Path
from typing import Any, Optional

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore

import yaml

# ML / GPU packages to detect
TORCH_PACKAGES = {"torch", "pytorch"}
TF_PACKAGES = {"tensorflow", "tf-keras"}
# Packages that require CUDA (no CPU fallback)
CUDA_MANDATORY_PACKAGES = {"bitsandbytes", "flash-attn", "flash_attn", "xformers"}
# Native build backends (require compiler/Rust)
NATIVE_BUILD_PATTERNS = ["maturin", "setuptools-rust", "pybind11"]
# Apple Silicon: packages with known x86-only or problematic wheels
ARM64_PROBLEMATIC = {"faiss-gpu", "faiss-cpu", "faiss"}  # faiss-gpu especially

ML_FRAMEWORKS = {
    "peft": "PEFT",
    "transformers": "Transformers",
    "diffusers": "Diffusers",
    "accelerate": "Accelerate",
    "torchao": "torchao",
    "mlx": "MLX",
}

# Packages that need system libs
LIBGL_PACKAGES = {"opencv-python", "opencv-contrib-python", "pyopengl", "opencv"}
FFMPEG_PACKAGES = {"ffmpeg-python", "av", "pyav", "ffmpeg"}

# Node native module patterns
NODE_NATIVE_PATTERNS = [
    r"node-gyp",
    r"nan\b",
    r"node-addon-api",
    r"@napi-rs/",
    r"prebuild",
    r"bindings\b",
    r"ffi-napi",
    r"ref-napi",
]


def _extract_version_constraint(s: str, pkg: str) -> str | None:
    """Extract version constraint for a package from a dep spec (e.g. torch>=2.2,<2.4)."""
    s = s.split("#")[0].strip()
    # Strip [extras] e.g. torch[cpu]
    s = re.sub(r"\[\s*[^\]]+\]\s*", "", s)
    # Match constraint: >=, <=, ==, ~=, etc.
    m = re.search(r"([>=<~!]+[\d.*,\s]+)", s)
    return m.group(1).strip() if m and m.group(1).strip() else None


def parse_requirements(path: Path) -> dict[str, Any]:
    """Parse requirements.txt for packages and constraints."""
    result: dict[str, Any] = {
        "packages": [],
        "package_versions": {},
        "uses_torch": False,
        "uses_tensorflow": False,
        "frameworks": [],
        "requires_libgl": False,
        "requires_ffmpeg": False,
        "cuda_mandatory_packages": [],
        "native_build_backends": [],
        "tensorflow_version": None,
    }
    if not path.exists():
        return result

    content = path.read_text(errors="replace")
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Handle -e, -r, -f
        if line.startswith("-"):
            continue
        # Extract package name (strip version specifiers)
        pkg = re.split(r"[\[\]>=<!=~\s]", line)[0].lower().replace("_", "-")
        if pkg:
            result["packages"].append(pkg)
        if any(t in pkg for t in TORCH_PACKAGES):
            result["uses_torch"] = True
            if "+cu" in line.lower() or "+cuda" in line.lower():
                result.setdefault("cuda_mandatory_packages", []).append("torch+cu")
        if any(t in pkg for t in TF_PACKAGES):
            result["uses_tensorflow"] = True
            cv = _extract_version_constraint(line, "tensorflow")
            if cv:
                result["tensorflow_version"] = cv
        if any(c in pkg for c in CUDA_MANDATORY_PACKAGES):
            result.setdefault("cuda_mandatory_packages", []).append(pkg)
        for key, name in ML_FRAMEWORKS.items():
            if key in pkg and name not in result["frameworks"]:
                result["frameworks"].append(name)
        if any(l in pkg for l in LIBGL_PACKAGES):
            result["requires_libgl"] = True
        if any(f in pkg for f in FFMPEG_PACKAGES):
            result["requires_ffmpeg"] = True
        # Version constraints for torch/torchao (for ML compatibility rules)
        if pkg in ("torch", "torchao"):
            constraint = _extract_version_constraint(line, pkg)
            if constraint:
                result["package_versions"][pkg] = constraint
        for nb in NATIVE_BUILD_PATTERNS:
            if nb in pkg:
                result.setdefault("native_build_backends", []).append(nb)
    return result


def parse_pyproject(path: Path) -> dict[str, Any]:
    """Parse pyproject.toml for Python version, deps, project name."""
    result: dict[str, Any] = {
        "name": "",
        "python_version": None,
        "uses_torch": False,
        "uses_tensorflow": False,
        "frameworks": [],
        "packages": [],
        "package_versions": {},
        "requires_libgl": False,
        "requires_ffmpeg": False,
        "cuda_mandatory_packages": [],
        "native_build_backends": [],
        "tensorflow_version": None,
    }
    if not path.exists():
        return result

    try:
        data = tomllib.loads(path.read_text())
    except Exception:
        return result

    # Project name
    if "project" in data:
        proj = data["project"]
        result["name"] = proj.get("name", "")
        if "requires-python" in proj:
            result["python_version"] = proj["requires-python"]
        deps = list(proj.get("dependencies", []))
        for opt_name, opt_deps in proj.get("optional-dependencies", {}).items():
            deps.extend(opt_deps)
        for dep in deps:
            dep_str = str(dep)
            pkg = re.split(r"[\[\]>=<!=~\s]", dep_str)[0].lower().replace("_", "-")
            if pkg and pkg not in result["packages"]:
                result["packages"].append(pkg)
            if any(t in pkg for t in TORCH_PACKAGES):
                result["uses_torch"] = True
                if "+cu" in dep_str.lower() or "+cuda" in dep_str.lower():
                    result.setdefault("cuda_mandatory_packages", []).append("torch+cu")
            if any(t in pkg for t in TF_PACKAGES):
                result["uses_tensorflow"] = True
                cv = _extract_version_constraint(dep_str, "tensorflow")
                if cv:
                    result["tensorflow_version"] = cv
            if any(c in pkg for c in CUDA_MANDATORY_PACKAGES):
                result.setdefault("cuda_mandatory_packages", []).append(pkg)
            for nb in NATIVE_BUILD_PATTERNS:
                if nb in pkg:
                    result.setdefault("native_build_backends", []).append(nb)
            for key, name in ML_FRAMEWORKS.items():
                if key in pkg and name not in result["frameworks"]:
                    result["frameworks"].append(name)
            if any(l in pkg for l in LIBGL_PACKAGES):
                result["requires_libgl"] = True
            if any(f in pkg for f in FFMPEG_PACKAGES):
                result["requires_ffmpeg"] = True
            if pkg in ("torch", "torchao"):
                constraint = _extract_version_constraint(dep_str, pkg)
                if constraint:
                    result["package_versions"][pkg] = constraint

    # Build system (maturin, setuptools-rust, pybind11)
    if "build-system" in data:
        build = data["build-system"]
        for req in build.get("requires", []):
            req_str = str(req).lower()
            for nb in NATIVE_BUILD_PATTERNS:
                if nb in req_str and nb not in result.get("native_build_backends", []):
                    result.setdefault("native_build_backends", []).append(nb)
        backend = str(build.get("build-backend", "")).lower()
        for nb in NATIVE_BUILD_PATTERNS:
            if nb in backend and nb not in result.get("native_build_backends", []):
                result.setdefault("native_build_backends", []).append(nb)

    # Tool.poetry
    if "tool" in data and "poetry" in data:
        poetry = data["tool"]["poetry"]
        if not result["name"]:
            result["name"] = poetry.get("name", "")
        if not result["python_version"] and "dependencies" in poetry:
            py = poetry["dependencies"].get("python")
            if py:
                result["python_version"] = str(py)

    return result


def parse_package_json(path: Path) -> dict[str, Any]:
    """Parse package.json for name, native modules, and engines."""
    result: dict[str, Any] = {"name": "", "native_modules": [], "engines_node": None, "has_deps": False}
    if not path.exists():
        return result

    try:
        data = json.loads(path.read_text())
    except Exception:
        return result

    result["name"] = data.get("name", "")
    engines = data.get("engines") or {}
    if isinstance(engines, dict) and engines.get("node"):
        result["engines_node"] = engines["node"]
    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
    result["has_deps"] = bool(deps)
    for pkg in deps:
        for pat in NODE_NATIVE_PATTERNS:
            if re.search(pat, pkg, re.I):
                result["native_modules"].append(pkg)
                break
    return result


def parse_cargo_toml(path: Path) -> dict[str, Any]:
    """Parse Cargo.toml for crate name and system libs."""
    result: dict[str, Any] = {"name": "", "system_libs": []}
    if not path.exists():
        return result

    try:
        data = tomllib.loads(path.read_text())
    except Exception:
        return result

    if "package" in data:
        result["name"] = data["package"].get("name", "")
    # Crates that typically need system libs
    SYSTEM_CRATES = {"openssl", "libssh2", "sqlite3", "sodiumoxide", "libgit2"}
    deps = {**data.get("dependencies", {}), **data.get("build-dependencies", {})}
    for dep in deps:
        if dep in SYSTEM_CRATES or "sys" in dep.lower():
            result["system_libs"].append(dep)
    return result


def parse_dockerfile(path: Path) -> dict[str, Any]:
    """Parse Dockerfile for base image, platform, Python."""
    result: dict[str, Any] = {"has_cuda": False, "python_version": None, "platform_amd64": False}
    if not path.exists():
        return result

    content = path.read_text(errors="replace")
    result["has_cuda"] = "cuda" in content.lower() or "nvidia" in content.lower()
    for line in content.splitlines():
        if "python:" in line.lower() or "python=" in line.lower():
            m = re.search(r"python[:\s]*([\d.]+)", line, re.I)
            if m:
                result["python_version"] = m.group(1)
        if "--platform=" in line.lower() or "platform=" in line.lower():
            if "amd64" in line.lower() or "x86_64" in line.lower():
                result["platform_amd64"] = True
    return result


def parse_setup_py(path: Path) -> dict[str, Any]:
    """Parse setup.py for python_requires."""
    result: dict[str, Any] = {"python_version": None}
    if not path.exists():
        return result

    content = path.read_text(errors="replace")
    m = re.search(r'python_requires\s*=\s*["\']([^"\']+)["\']', content)
    if m:
        result["python_version"] = m.group(1)
    return result


def parse_docker_compose(path: Path) -> dict[str, Any]:
    """Extract exposed ports from docker-compose.yml."""
    result: dict[str, Any] = {"ports": []}
    if not path.exists():
        return result
    try:
        data = yaml.safe_load(path.read_text())
    except Exception:
        return result
    if not data:
        return result

    def extract_ports(obj: Any, seen: set[int]) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in ("ports", "expose") and isinstance(v, list):
                    for p in v:
                        if isinstance(p, str) and ":" in p:
                            try:
                                _, host = p.split(":", 1)
                                port = int(host.split("-")[0].strip())
                                if 1 <= port <= 65535 and port not in seen:
                                    seen.add(port)
                                    result["ports"].append(port)
                            except (ValueError, IndexError):
                                pass
                        elif isinstance(p, int) and 1 <= p <= 65535 and p not in seen:
                            seen.add(p)
                            result["ports"].append(p)
                else:
                    extract_ports(v, seen)
        elif isinstance(obj, list):
            for item in obj:
                extract_ports(item, seen)

    extract_ports(data, set())
    return result


def parse_env(path: Path) -> dict[str, Any]:
    """Extract PORT and *_PORT from .env."""
    result: dict[str, Any] = {"ports": []}
    if not path.exists():
        return result
    try:
        content = path.read_text()
    except Exception:
        return result
    import re as re_mod
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re_mod.match(r"(?:PORT|[\w]+_PORT)\s*=\s*(\d+)", line, re_mod.I)
        if m:
            port = int(m.group(1))
            if 1 <= port <= 65535 and port not in result["ports"]:
                result["ports"].append(port)
    return result


def parse_workflow(path: Path) -> dict[str, Any]:
    """Parse a GitHub workflow YAML."""
    result: dict[str, Any] = {"runs_on": [], "has_cuda": False, "python_versions": []}
    if not path.exists():
        return result

    try:
        data = yaml.safe_load(path.read_text())
    except Exception:
        return result

    if not data:
        return result
    jobs = data.get("jobs", {})
    for job in jobs.values():
        if isinstance(job, dict):
            runs = job.get("runs-on", [])
            if isinstance(runs, str):
                runs = [runs]
            result["runs_on"].extend(runs)
            # Extract Python from strategy.matrix
            strat = job.get("strategy", {}) or {}
            matrix = strat.get("matrix", {}) or {}
            for key in ("python-version", "python_version", "python"):
                vals = matrix.get(key)
                if vals:
                    if isinstance(vals, list):
                        result["python_versions"].extend(str(v) for v in vals)
                    elif isinstance(vals, str):
                        result["python_versions"].append(vals)
            steps = job.get("steps", [])
            for step in steps:
                if isinstance(step, dict):
                    run = str(step.get("run", "")) + str(step.get("uses", ""))
                    result["has_cuda"] = result["has_cuda"] or "cuda" in run.lower() or "nvidia" in run.lower()
    return result
