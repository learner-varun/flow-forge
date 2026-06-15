from statistics import mean
from typing import Dict, List


def percentile(values: List[float], percent: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * percent
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    if lower == upper:
        return ordered[lower]
    weight = index - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def timing_summary(values: List[float]) -> Dict[str, float]:
    if not values:
        return {"min": 0, "avg": 0, "p90": 0, "p95": 0, "max": 0}
    return {
        "min": round(min(values), 2),
        "avg": round(mean(values), 2),
        "p90": round(percentile(values, 0.90), 2),
        "p95": round(percentile(values, 0.95), 2),
        "max": round(max(values), 2),
    }
