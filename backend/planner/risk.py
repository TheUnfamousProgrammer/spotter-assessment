"""Weather risk rules from the assessment, one level per checkpoint.

A shared boundary (e.g. rain 0.25) belongs to the higher band; the brief's
strict ">" on the top rain/snow band and on load weights is taken literally.
"""

LOW, MODERATE, HIGH, SEVERE, NO_TRAVEL = range(5)
LEVELS = ["Low", "Moderate", "High", "Severe", "No Travel"]


def wind_level(mph):
    for threshold, level in ((55, NO_TRAVEL), (45, SEVERE), (35, HIGH), (25, MODERATE)):
        if mph >= threshold:
            return level
    return LOW


def rain_level(in_hr):
    if in_hr > 1.00:
        return NO_TRAVEL
    for threshold, level in ((0.50, SEVERE), (0.25, HIGH), (0.10, MODERATE)):
        if in_hr >= threshold:
            return level
    return LOW


def snow_level(in_hr):
    if in_hr > 3.0:
        return NO_TRAVEL
    for threshold, level in ((2.0, SEVERE), (1.0, HIGH), (0.5, MODERATE)):
        if in_hr >= threshold:
            return level
    return LOW


def load_level(wind_mph, load_lb):
    if wind_mph >= 55 or (wind_mph >= 45 and load_lb > 30_000):
        return NO_TRAVEL
    if wind_mph >= 35 and load_lb > 40_000:
        return SEVERE
    return LOW


def factor_levels(wind_mph, rain_in_hr, snow_in_hr, load_lb):
    """Level of each condition on its own; the load rule can only raise the wind level."""
    return {
        "wind": max(wind_level(wind_mph), load_level(wind_mph, load_lb)),
        "rain": rain_level(rain_in_hr),
        "snow": snow_level(snow_in_hr),
    }


def assess(wind_mph, rain_in_hr, snow_in_hr, load_lb):
    """Return (level, reason): the worst of wind, rain, snow and the load rule."""
    levels = factor_levels(wind_mph, rain_in_hr, snow_in_hr, load_lb)
    load_raised = levels["wind"] > wind_level(wind_mph)
    factors = [
        (levels["wind"], f"Wind {wind_mph:.0f} mph" + (f" with {load_lb:,} lb load" if load_raised else "")),
        (levels["rain"], f"Rain {rain_in_hr:.2f} in/hr"),
        (levels["snow"], f"Snow {snow_in_hr:.2f} in/hr"),
    ]
    level = max(lvl for lvl, _ in factors)
    if level == LOW:
        return LOW, "Within safe limits"
    return level, " · ".join(text for lvl, text in factors if lvl == level)
