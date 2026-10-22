"""Route summaries and the recommendation order from the brief.

No Travel miles come first: the brief's list starts at Severe, but a route
the rules forbid must never beat one they allow.
"""

from .risk import HIGH, NO_TRAVEL, SEVERE

# (summary field, wording for the reason)
CRITERIA = [
    ("no_travel_mi", "Fewest No Travel miles"),
    ("severe_mi", "Fewest Severe miles"),
    ("high_mi", "Fewest High miles"),
    ("avg_risk", "Lowest average risk"),
    ("duration_s", "travel time"),
]


def summarize(checkpoints, duration_s):
    """Checkpoints carry `level` and `miles` (the stretch of road they stand for).

    Values are rounded so float noise cannot decide a tie: near-ties fall
    through to the next criterion, as the brief's order intends.
    """
    by_level = [0.0] * 5
    for cp in checkpoints:
        by_level[cp["level"]] += cp["miles"]
    total = sum(by_level)
    return {
        "no_travel_mi": round(by_level[NO_TRAVEL], 1),
        "severe_mi": round(by_level[SEVERE], 1),
        "high_mi": round(by_level[HIGH], 1),
        "avg_risk": round(sum(lvl * mi for lvl, mi in enumerate(by_level)) / total, 2) if total else 0.0,
        "duration_s": round(duration_s),
    }


def rank(summaries):
    """Return (indices best-first, one-sentence reason the best one won)."""
    keys = [tuple(s[field] for field, _ in CRITERIA) for s in summaries]
    order = sorted(range(len(keys)), key=keys.__getitem__)
    if len(order) == 1:
        return order, "Only route available."
    best, runner_up = keys[order[0]], keys[order[1]]
    for (field, label), a, b in zip(CRITERIA, best, runner_up):
        if a != b:
            if field == "duration_s":
                return order, f"Same risk as the next best route and {round((b - a) / 60)} min faster."
            return order, f"{label}: {a:g} vs {b:g} on the next best route."
    return order, "Tied with the next best route on every criterion."
