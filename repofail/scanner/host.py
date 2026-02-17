"""Host inspector — detects OS, arch, CUDA, Python, Node, Rust, compiler, RAM."""

import platform
import shutil
import subprocess
from pathlib import Path

from ..models import HostProfile


def inspect_host() -> HostProfile:
    """Inspect the current machine and return a HostProfile."""
    system = platform.system().lower()
    if system == "darwin":
        os_name = "macos"
    elif system == "windows":
        os_name = "windows"
    else:
        os_name = "linux"

    machine = platform.machine().lower()
    if machine in ("arm64", "aarch64", "arm"):
        arch = "arm64"
    else:
        arch = "x86_64"

    cuda_available = False
    cuda_version = None
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            cuda_available = True
            # nvidia-smi gives driver version; CUDA version is separate
            cuda_version = result.stdout.strip().split("\n")[0].strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    python_version = None
    try:
        python_version = platform.python_version()
    except Exception:
        pass

    has_compiler = bool(shutil.which("gcc") or shutil.which("clang") or shutil.which("cc"))

    ram_gb = _get_ram_gb()

    node_version = _get_version("node", ["--version"])  # "v20.10.0"
    rust_version = _get_version("rustc", ["--version"], version_index=1)  # "rustc 1.75.0 ..."

    has_metal = _has_metal()
    has_libgl = _has_libgl()
    has_ffmpeg = _has_ffmpeg()

    return HostProfile(
        os=os_name,
        arch=arch,
        cuda_available=cuda_available,
        cuda_version=cuda_version,
        python_version=python_version,
        node_version=node_version,
        rust_version=rust_version,
        has_compiler=has_compiler,
        has_metal=has_metal,
        has_libgl=has_libgl,
        has_ffmpeg=has_ffmpeg,
        ram_gb=ram_gb,
    )


def _get_version(cmd: str, args: list[str], version_index: int = 0) -> str | None:
    """Get version string from a command (e.g. node --version)."""
    try:
        result = subprocess.run(
            [cmd, *args],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split()
            return parts[version_index] if len(parts) > version_index else parts[0]
    except (FileNotFoundError, subprocess.TimeoutExpired, IndexError):
        pass
    return None


def _has_metal() -> bool:
    """macOS has Metal (GPU) built-in."""
    return platform.system() == "Darwin"


def _has_libgl() -> bool:
    """Check for libGL (OpenGL)."""
    try:
        if platform.system() == "Linux":
            result = subprocess.run(
                ["ldconfig", "-p"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            return "libGL" in (result.stdout or "") if result.returncode == 0 else False
        if platform.system() == "Darwin":
            return True  # OpenGL framework on macOS
    except Exception:
        pass
    return False


def _has_ffmpeg() -> bool:
    """Check if ffmpeg is available."""
    return bool(shutil.which("ffmpeg"))


def is_port_in_use(port: int) -> bool:
    """Check if a port is already bound (something is listening)."""
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", port))
            return False
    except OSError:
        return True


def _get_ram_gb() -> float | None:
    """Get total RAM in GB if detectable. Returns None on Windows or if detection fails."""
    try:
        if platform.system() == "Darwin":
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                return int(result.stdout.strip()) / (1024**3)
        elif platform.system() == "Linux":
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        return kb / (1024**2)
        elif platform.system() == "Windows":
            # wmic is deprecated; fallback would need psutil. Graceful: return None.
            pass
    except Exception:
        pass
    return None
