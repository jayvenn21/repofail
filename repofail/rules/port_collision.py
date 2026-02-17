"""Rule: Port collision risk in multi-service repo."""

from ..models import HostProfile, RepoProfile
from ..scanner.host import is_port_in_use
from .base import RuleResult, Severity


def check(repo: RepoProfile, host: HostProfile) -> RuleResult | None:
    """If repo requires ports that are already in use on host, flag HIGH."""
    if not repo.required_ports:
        return None

    in_use = [p for p in repo.required_ports if is_port_in_use(p)]
    if not in_use:
        return None

    return RuleResult(
        rule_id="port_collision_risk",
        severity=Severity.HIGH,
        message="Required service port already in use.",
        reason=f"Port(s) {', '.join(map(str, in_use))} already bound. Startup will fail.",
        host_summary=f"{host.os} {host.arch}",
        evidence={
            "required_ports": repo.required_ports,
            "ports_in_use": in_use,
        },
        category="runtime_environment",
    )
