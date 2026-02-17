"""Local failure telemetry — opt-in, no cloud."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# ~/.repofail/reports/
REPORTS_DIR = Path.home() / ".repofail" / "reports"


@dataclass
class FailureReport:
    """Anonymized failure report — no paths, no repo details beyond name."""

    timestamp: str
    repo_name: str
    rule_ids: list[str]
    severities: list[str]
    host_os: str
    host_arch: str
    host_cuda: bool
    host_python: str | None

    def to_dict(self) -> dict:
        return asdict(self)


def save_report(
    repo_name: str,
    rule_results: list,
    host: "HostProfile",
) -> Path | None:
    """Save a failure report to local storage. Returns path if saved."""
    if not rule_results:
        return None
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report = FailureReport(
        timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        repo_name=repo_name or "unknown",
        rule_ids=[r.rule_id for r in rule_results],
        severities=[r.severity.value for r in rule_results],
        host_os=host.os,
        host_arch=host.arch,
        host_cuda=host.cuda_available,
        host_python=host.python_version,
    )
    path = REPORTS_DIR / f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(report.to_dict(), indent=2))
    return path


def load_reports() -> list[dict]:
    """Load all local reports."""
    if not REPORTS_DIR.exists():
        return []
    reports = []
    for f in sorted(REPORTS_DIR.glob("*.json")):
        try:
            reports.append(json.loads(f.read_text()))
        except (json.JSONDecodeError, OSError):
            pass
    return reports


def get_stats() -> dict:
    """Aggregate local reports into stats."""
    reports = load_reports()
    if not reports:
        return {"total_runs": 0, "by_rule": {}, "by_host": {}}

    by_rule: dict[str, int] = {}
    by_host: dict[str, int] = {}
    total = 0

    for r in reports:
        total += 1
        for rule_id in r.get("rule_ids", []):
            by_rule[rule_id] = by_rule.get(rule_id, 0) + 1
        key = f"{r.get('host_os', '?')} {r.get('host_arch', '?')}"
        if r.get("host_cuda"):
            key += " cuda"
        else:
            key += " no-cuda"
        by_host[key] = by_host.get(key, 0) + 1

    return {
        "total_runs": total,
        "by_rule": by_rule,
        "by_host": by_host,
    }
