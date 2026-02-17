"""Structured profiles for repo and host."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class HostProfile:
    """Structured output from host inspection."""

    os: str  # "macos", "linux", "windows"
    arch: str  # "arm64", "x86_64"
    cuda_available: bool = False
    cuda_version: Optional[str] = None
    python_version: Optional[str] = None
    node_version: Optional[str] = None
    rust_version: Optional[str] = None
    has_compiler: bool = False  # gcc/clang for native builds
    has_metal: bool = False  # macOS Metal / MLX
    has_libgl: bool = False
    has_ffmpeg: bool = False
    ram_gb: Optional[float] = None


@dataclass
class RepoProfile:
    """Structured output from repo scanning."""

    path: str
    name: str = ""

    # Python
    python_version: Optional[str] = None  # e.g. ">=3.10,<3.12"
    has_requirements_txt: bool = False
    has_pyproject: bool = False
    has_setup_py: bool = False

    # ML / GPU
    uses_torch: bool = False
    uses_tensorflow: bool = False
    requires_cuda: bool = False  # explicit CUDA in code/config
    cuda_optional: bool = True  # has CPU fallback
    cuda_mandatory_packages: list[str] = field(default_factory=list)  # bitsandbytes, flash-attn, etc.
    frameworks: list[str] = field(default_factory=list)  # PEFT, diffusers, etc.

    # Other ecosystems
    has_package_json: bool = False
    node_engine_spec: str | None = None  # engines.node from package.json, e.g. ">=18"
    node_lock_file_missing: bool = False  # package.json has deps but no package-lock.json/yarn.lock
    node_native_modules: list[str] = field(default_factory=list)
    has_cargo_toml: bool = False
    rust_system_libs: list[str] = field(default_factory=list)

    # System libs (detected from deps)
    requires_libgl: bool = False
    requires_ffmpeg: bool = False

    # Infra
    has_dockerfile: bool = False
    dockerfile_has_cuda: bool = False  # FROM nvidia/cuda or cuda in Dockerfile
    has_devcontainer: bool = False  # .devcontainer/ or devcontainer.json
    docker_platform_amd64: bool = False  # FROM --platform=linux/amd64
    required_ports: list[int] = field(default_factory=list)  # from docker-compose, .env
    github_workflows: list[str] = field(default_factory=list)
    os_specific: bool = False

    # For rule output — where CUDA usage was found
    cuda_files: list[str] = field(default_factory=list)
    cuda_usages: list[dict] = field(default_factory=list)  # [{"file": str, "line": int, "kind": str}]

    # Monorepo: discovered subprojects (path rel to repo, type, key fields)
    subprojects: list[dict] = field(default_factory=list)

    # Raw data for rule engine
    raw: dict = field(default_factory=dict)
