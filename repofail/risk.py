"""Probabilistic failure risk estimation — deterministic, explainable."""

from .rules.base import RuleResult, Severity


# Confidence levels (rule-driven, defensible):
# HIGH  = Deterministic spec violation or hardcoded mismatch (direct read from config/code)
# MEDIUM = Structural inference (monorepo, multiple subprojects, context-dependent)
# LOW   = Heuristic / incomplete signals (minimal evidence, guess from layout)
#
# Per-rule confidence multiplies severity penalty: high=1.0, medium=0.75, low=0.5

# Severity weights: reduction in success probability per finding
# 0% reserved for: CUDA hardcoded, engine mismatch, python version violation, docker amd64 on arm64
SEVERITY_WEIGHTS = {
    Severity.HIGH: 45,
    Severity.MEDIUM: 20,
    Severity.LOW: 7,
    Severity.INFO: 5,
}

# Per-rule weight override (calibrated: deterministic = higher, probabilistic = lower)
RULE_WEIGHTS = {
    "node_engine_mismatch": 50,
    "lock_file_missing": 40,
    "spec_drift": 25,
}

# Per-rule determinism (1.0 = will break, 0.6 = probabilistic)
RULE_DETERMINISM = {
    "spec_drift": 0.6,
}

# Confidence multiplier: reduces penalty when evidence is heuristic
# high=1.0 (full penalty), medium=0.75, low=0.5
CONFIDENCE_MULTIPLIER = {"high": 1.0, "medium": 0.75, "low": 0.5}


def run_confidence(results: list[RuleResult]) -> tuple[str, list[str]]:
    """
    Per-run confidence from results.
    High if at least one HIGH or many deterministic rules.
    Medium if mixed heuristics. Low if minimal evidence.
    Returns (aggregate, low_confidence_rule_ids).
    """
    if not results:
        return "high", []
    has_high = any(r.severity == Severity.HIGH for r in results)
    high_conf_count = sum(1 for r in results if getattr(r, "confidence", "high") == "high")
    if has_high or high_conf_count >= len(results) * 0.8:
        agg = "high"
    elif len(results) >= 3 or high_conf_count >= 1:
        agg = "medium"
    else:
        agg = "low"
    low = [r.rule_id for r in results if getattr(r, "confidence", "high") == "low"]
    return agg, low


# Cap total penalty so score doesn't flatten across 3 vs 7 HIGH
MAX_PENALTY = 90


def _all_high_rules_deterministic(results: list[RuleResult]) -> bool:
    """True if every HIGH rule has determinism = 1.0. Else floor at 10%."""
    from .rules.base import Severity
    high_rules = [r for r in results if r.severity == Severity.HIGH]
    if not high_rules:
        return True
    for r in high_rules:
        det = RULE_DETERMINISM.get(r.rule_id, 1.0)
        if det < 1.0:
            return False
    return True


def estimate_success_probability(results: list[RuleResult]) -> int:
    """
    Estimate run success probability (0-100) from rule results.
    penalty = weight × confidence × determinism.
    If ALL HIGH rules are determinism=1.0 → allow 0% (rare, powerful).
    If ANY HIGH has determinism<1.0 (e.g. spec_drift) → cap penalty, floor at 10%.
    """
    if not results:
        return 100
    total_penalty = 0
    for r in results:
        weight = RULE_WEIGHTS.get(r.rule_id) or SEVERITY_WEIGHTS.get(r.severity, 0)
        conf = CONFIDENCE_MULTIPLIER.get(getattr(r, "confidence", "high"), 1.0)
        det = RULE_DETERMINISM.get(r.rule_id, 1.0)
        total_penalty += weight * conf * det
    if not _all_high_rules_deterministic(results):
        total_penalty = min(total_penalty, MAX_PENALTY)
    raw = round(100 - total_penalty)
    if not _all_high_rules_deterministic(results):
        raw = max(10, raw)
    return max(0, min(100, raw))
