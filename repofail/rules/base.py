"""Base types for rules."""

from dataclasses import dataclass
from enum import Enum


class Severity(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


# Rule categories for scalability and filtering
RULE_CATEGORIES = (
    "spec_violation",        # Python version, requires-python
    "hardware_incompatibility",  # CUDA, GPU, ARM64 wheels
    "toolchain_missing",     # compiler, Rust, node-gyp
    "runtime_environment",   # port collision, RAM, Docker
    "architecture_mismatch",  # Apple Silicon, x86-only
)


@dataclass
class RuleResult:
    """Output of a single rule check."""

    rule_id: str
    severity: Severity
    message: str
    reason: str  # Specific: file paths, host details
    host_summary: str = ""  # e.g. "macOS arm64, no NVIDIA driver"
    confidence: str = "high"  # high=direct read, medium=inferred, low=heuristic
    evidence: dict | None = None  # Auditable: e.g. {"docker_python": "3.11", "host_python": "3.12"}
    category: str = ""  # spec_violation | hardware_incompatibility | toolchain_missing | runtime_environment | architecture_mismatch
