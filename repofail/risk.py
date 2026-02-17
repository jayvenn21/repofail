"""Probabilistic failure risk estimation — deterministic, explainable."""

from .rules.base import RuleResult, Severity


# Confidence levels (rule-driven, defensible):
# HIGH  = Deterministic spec violation or hardcoded mismatch (direct read from config/code)
# MEDIUM = Structural inference (monorepo, multiple subprojects, context-dependent)
# LOW   = Heuristic / incomplete signals (minimal evidence, guess from layout)
#
# Per-rule confidence multiplies severity penalty: high=1.0, medium=0.75, low=0.5

# Severity weights: reduction in success probability per finding
# Deterministic, no overfitting. Score = 100 - sum(weights), clamp 0-100.
SEVERITY_WEIGHTS = {
    Severity.HIGH: 45,
    Severity.MEDIUM: 20,
    Severity.LOW: 7,
    Severity.INFO: 5,
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


def estimate_success_probability(results: list[RuleResult]) -> int:
    """
    Estimate run success probability (0-100) from rule results.
    score = 100 - sum(SEVERITY_WEIGHTS[severity] * CONFIDENCE_MULTIPLIER[confidence])
    Clamped to 0-100.
    """
    if not results:
        return 100
    total_penalty = 0
    for r in results:
        weight = SEVERITY_WEIGHTS.get(r.severity, 0)
        mult = CONFIDENCE_MULTIPLIER.get(getattr(r, "confidence", "high"), 1.0)
        total_penalty += weight * mult
    return max(0, min(100, round(100 - total_penalty)))
