"""Repo scanner — discovers configs recursively, parses, merges profiles."""

from pathlib import Path

from ..models import RepoProfile
from .ast_scan import scan_python_tree
from .parsers import (
    parse_cargo_toml,
    parse_docker_compose,
    parse_dockerfile,
    parse_env,
    parse_package_json,
    parse_pyproject,
    parse_requirements,
    parse_setup_py,
    parse_workflow,
)

SKIP_PARTS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".tox", "build", "dist", "eggs"}
MAX_CONFIGS = 20  # Cap discovery to avoid huge monorepos


def _should_skip(path: Path, repo_root: Path) -> bool:
    """Skip paths inside ignored directories."""
    try:
        rel = path.relative_to(repo_root)
    except ValueError:
        return True
    return any(part in rel.parts for part in SKIP_PARTS)


def _discover_configs(repo_path: Path) -> dict[str, list[Path]]:
    """Recursively discover config files. Returns {type: [paths]}."""
    found: dict[str, list[Path]] = {
        "pyproject": [],
        "requirements": [],
        "setup_py": [],
        "package_json": [],
        "cargo": [],
        "dockerfile": [],
        "docker_compose": [],
        "env": [],
    }
    count = 0
    for pattern, key in [
        ("pyproject.toml", "pyproject"),
        ("requirements*.txt", "requirements"),
        ("setup.py", "setup_py"),
        ("package.json", "package_json"),
        ("Cargo.toml", "cargo"),
        ("Dockerfile", "dockerfile"),
        ("docker-compose*.yml", "docker_compose"),
        ("docker-compose*.yaml", "docker_compose"),
        (".env", "env"),
    ]:
        for p in repo_path.rglob(pattern):
            if count >= MAX_CONFIGS:
                return found
            if _should_skip(p, repo_path):
                continue
            found[key].append(p)
            count += 1
    # Prefer root-level configs (for name resolution)
    for key in found:
        found[key] = sorted(
            found[key],
            key=lambda p: (p.parent != repo_path, len(p.relative_to(repo_path).parts)),
        )
    return found


def _project_root(config_path: Path) -> Path:
    """Directory containing this config (project root for that subproject)."""
    return config_path.parent


def _is_root(path: Path, repo_root: Path) -> bool:
    """True if path is repo root."""
    try:
        return path.resolve() == repo_root.resolve()
    except ValueError:
        return False


def _is_generic_name(name: str) -> bool:
    """True if name looks like a template/default (my-app, t3-app, etc.)."""
    if not name:
        return True
    lower = name.lower()
    return (
        lower.startswith("my-")
        or lower.startswith("my_")
        or "t3-" in lower
        or "template" in lower
        or lower in ("app", "web", "frontend", "project")
    )


def _rel_path(path: Path, repo_root: Path) -> str:
    """Relative path string, or '.' for root."""
    try:
        rel = path.relative_to(repo_root)
        return str(rel) if str(rel) != "." else "."
    except ValueError:
        return str(path)


def scan_repo(path: str | Path) -> RepoProfile:
    """Scan a repository recursively; discover subprojects, merge profiles."""
    repo_path = Path(path).resolve()
    if not repo_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {repo_path}")

    profile = RepoProfile(path=str(repo_path), name="")
    configs = _discover_configs(repo_path)

    # Track project roots we've seen (avoid duplicate subprojects)
    seen_roots: set[Path] = set()
    python_versions: list[str] = []

    def add_subproject(root: Path, ptype: str, **kwargs) -> None:
        rel = _rel_path(root, repo_path)
        if root not in seen_roots:
            seen_roots.add(root)
            profile.subprojects.append({"path": rel, "type": ptype, **kwargs})

    # Pyproject
    for p in configs["pyproject"]:
        root = _project_root(p)
        data = parse_pyproject(p)
        if data["name"] and not profile.name:
            profile.name = data["name"]
        if data["python_version"]:
            profile.python_version = profile.python_version or data["python_version"]
            python_versions.append(data["python_version"])
        profile.uses_torch = profile.uses_torch or data["uses_torch"]
        profile.uses_tensorflow = profile.uses_tensorflow or data["uses_tensorflow"]
        for fw in data["frameworks"]:
            if fw not in profile.frameworks:
                profile.frameworks.append(fw)
        profile.requires_libgl = profile.requires_libgl or data.get("requires_libgl", False)
        profile.requires_ffmpeg = profile.requires_ffmpeg or data.get("requires_ffmpeg", False)
        for pkg in data.get("cuda_mandatory_packages", []):
            if pkg not in profile.cuda_mandatory_packages:
                profile.cuda_mandatory_packages.append(pkg)
        for nb in data.get("native_build_backends", []):
            profile.raw.setdefault("native_build_backends", [])
            if nb not in profile.raw["native_build_backends"]:
                profile.raw["native_build_backends"].append(nb)
        profile.has_pyproject = True
        add_subproject(root, "python", python_version=data.get("python_version"))
        profile.raw.setdefault("pyproject", {})  # keep first/merged; subprojects in raw
        if "pyproject" not in profile.raw or not profile.raw["pyproject"]:
            profile.raw["pyproject"] = data

    # Requirements
    for p in configs["requirements"]:
        root = _project_root(p)
        data = parse_requirements(p)
        profile.uses_torch = profile.uses_torch or data["uses_torch"]
        profile.uses_tensorflow = profile.uses_tensorflow or data["uses_tensorflow"]
        for fw in data["frameworks"]:
            if fw not in profile.frameworks:
                profile.frameworks.append(fw)
        profile.requires_libgl = profile.requires_libgl or data.get("requires_libgl", False)
        profile.requires_ffmpeg = profile.requires_ffmpeg or data.get("requires_ffmpeg", False)
        for pkg in data.get("cuda_mandatory_packages", []):
            if pkg not in profile.cuda_mandatory_packages:
                profile.cuda_mandatory_packages.append(pkg)
        for nb in data.get("native_build_backends", []):
            profile.raw.setdefault("native_build_backends", [])
            if nb not in profile.raw["native_build_backends"]:
                profile.raw["native_build_backends"].append(nb)
        profile.has_requirements_txt = True
        if root not in seen_roots:
            add_subproject(root, "python")
        profile.raw.setdefault("requirements", data)

    # Setup.py
    for p in configs["setup_py"]:
        root = _project_root(p)
        data = parse_setup_py(p)
        if data["python_version"] and not profile.python_version:
            profile.python_version = data["python_version"]
            python_versions.append(data["python_version"])
        profile.has_setup_py = True
        add_subproject(root, "python", python_version=data.get("python_version"))
        profile.raw.setdefault("setup_py", data)

    # Package.json (skip generic names like my-t3-app — prefer folder name)
    for p in configs["package_json"]:
        root = _project_root(p)
        data = parse_package_json(p)
        if data["name"] and not profile.name and not _is_generic_name(data["name"]):
            profile.name = data["name"]
        profile.node_native_modules = list(
            dict.fromkeys(profile.node_native_modules + data.get("native_modules", []))
        )
        if data.get("engines_node") and not profile.node_engine_spec:
            profile.node_engine_spec = data["engines_node"]
        if data.get("has_deps") and not (root / "package-lock.json").exists() and not (root / "yarn.lock").exists():
            profile.node_lock_file_missing = True
        profile.has_package_json = True
        add_subproject(root, "node")
        profile.raw.setdefault("package_json", data)

    # Cargo
    for p in configs["cargo"]:
        root = _project_root(p)
        data = parse_cargo_toml(p)
        if data["name"] and not profile.name:
            profile.name = data["name"]
        profile.rust_system_libs = list(
            dict.fromkeys(profile.rust_system_libs + data.get("system_libs", []))
        )
        profile.has_cargo_toml = True
        add_subproject(root, "rust")
        profile.raw.setdefault("cargo", data)

    # Dockerfile
    for p in configs["dockerfile"]:
        root = _project_root(p)
        data = parse_dockerfile(p)
        profile.has_dockerfile = True
        profile.dockerfile_has_cuda = profile.dockerfile_has_cuda or data.get("has_cuda", False)
        profile.docker_platform_amd64 = profile.docker_platform_amd64 or data.get("platform_amd64", False)
        if data["python_version"] and not profile.python_version:
            profile.python_version = data["python_version"]
        add_subproject(root, "docker")
        profile.raw.setdefault("dockerfile", data)

    # Devcontainer
    profile.has_devcontainer = (
        (repo_path / ".devcontainer" / "devcontainer.json").exists()
        or (repo_path / ".devcontainer.json").exists()
    )

    # Docker Compose and .env (root only for ports)
    for p in (repo_path / "docker-compose.yml", repo_path / "docker-compose.yaml"):
        if p.exists():
            data = parse_docker_compose(p)
            for port in data.get("ports", []):
                if port not in profile.required_ports:
                    profile.required_ports.append(port)
            break
    env_path = repo_path / ".env"
    if env_path.exists():
        data = parse_env(env_path)
        for port in data.get("ports", []):
            if port not in profile.required_ports:
                profile.required_ports.append(port)

    # .github/workflows (root only)
    workflows_path = repo_path / ".github" / "workflows"
    if workflows_path.is_dir():
        for wf in workflows_path.glob("*.yml"):
            profile.github_workflows.append(wf.stem)
            profile.raw.setdefault("workflows", {})[wf.stem] = parse_workflow(wf)
        for wf in workflows_path.glob("*.yaml"):
            if wf.stem not in profile.github_workflows:
                profile.github_workflows.append(wf.stem)
                profile.raw.setdefault("workflows", {})[wf.stem] = parse_workflow(wf)

    # Python AST scan
    ast_data = scan_python_tree(repo_path)
    profile.uses_torch = profile.uses_torch or ast_data["uses_torch"]
    profile.uses_tensorflow = profile.uses_tensorflow or ast_data["uses_tensorflow"]
    if ast_data["requires_cuda"]:
        profile.requires_cuda = True
        profile.cuda_optional = ast_data.get("cuda_optional", False)
        profile.cuda_files = list(dict.fromkeys(ast_data.get("cuda_files", [])))
        profile.cuda_usages = ast_data.get("cuda_usages", [])
    if profile.cuda_mandatory_packages:
        profile.requires_cuda = True
        profile.cuda_optional = False  # bitsandbytes etc have no CPU fallback

    if profile.raw.get("workflows"):
        for wf_data in profile.raw["workflows"].values():
            runs = wf_data.get("runs_on", [])
            if any("windows" in str(r).lower() for r in runs):
                profile.os_specific = True
                break

    if not profile.name:
        profile.name = _derive_repo_name(repo_path)

    return profile


def _derive_repo_name(repo_path: Path) -> str:
    """
    Fallback repo name: directory name, humanized.
    'my-project' -> 'my-project', 'AutoGPT' -> 'AutoGPT'.
    """
    name = repo_path.name
    if not name or name == ".":
        return "repository"
    return name
