"""Load optional rules from YAML. Step 3 — extensible, community-driven."""

from pathlib import Path
from typing import Any

from ..models import HostProfile, RepoProfile
from .base import RuleResult, Severity

try:
    import yaml
except ImportError:
    yaml = None


def _repo_value(repo: RepoProfile, key: str) -> Any:
    """Get value from repo by dotted key."""
    parts = key.split(".")
    obj = repo
    for p in parts:
        obj = getattr(obj, p, None)
        if obj is None:
            return None
    return obj


def _host_value(host: HostProfile, key: str) -> Any:
    """Get value from host by dotted key."""
    parts = key.split(".")
    obj = host
    for p in parts:
        obj = getattr(obj, p, None)
        if obj is None:
            return None
    return obj


def _match(when: dict, repo: RepoProfile, host: HostProfile) -> bool:
    """Check if when conditions match. Simple key: value equality."""
    for k, v in when.items():
        if k.startswith("repo."):
            val = _repo_value(repo, k[5:])
        elif k.startswith("host."):
            val = _host_value(host, k[5:])
        else:
            continue
        if val != v:
            return False
    return True


def load_yaml_rules(repo_path: Path) -> list[dict]:
    """Load rules from .repofail/rules.yaml or repofail-rules.yaml in repo."""
    if not yaml:
        return []
    for p in [repo_path / ".repofail" / "rules.yaml", repo_path / "repofail-rules.yaml"]:
        if p.exists():
            try:
                data = yaml.safe_load(p.read_text())
                if isinstance(data, list):
                    return data
                if isinstance(data, dict) and "rules" in data:
                    return data["rules"]
            except Exception:
                pass
    return []


def run_yaml_rules(repo: RepoProfile, host: HostProfile, repo_path: Path) -> list[RuleResult]:
    """Run YAML rules from repo, return any that fire."""
    rules = load_yaml_rules(Path(repo.path))
    results = []
    for r in rules:
        if not isinstance(r, dict) or "id" not in r or "when" not in r:
            continue
        when = r.get("when", {})
        if not _match(when, repo, host):
            continue
        sev = r.get("severity", "MEDIUM").upper()
        try:
            severity = Severity(sev)
        except ValueError:
            severity = Severity.MEDIUM
        results.append(RuleResult(
            rule_id=r["id"],
            severity=severity,
            message=r.get("explanation", r.get("message", "Custom rule fired."))[:200],
            reason=r.get("reason", ""),
            host_summary=f"{host.os} {host.arch}",
        ))
    return results
