import pytest

from planner.risk import HIGH, LOW, MODERATE, NO_TRAVEL, SEVERE, assess, rain_level, snow_level, wind_level


@pytest.mark.parametrize("mph,level", [
    (0, LOW), (24.9, LOW), (25, MODERATE), (34.9, MODERATE), (35, HIGH),
    (44.9, HIGH), (45, SEVERE), (54.9, SEVERE), (55, NO_TRAVEL),
])
def test_wind(mph, level):
    assert wind_level(mph) == level


@pytest.mark.parametrize("inches,level", [
    (0, LOW), (0.099, LOW), (0.10, MODERATE), (0.25, HIGH), (0.50, SEVERE),
    (1.00, SEVERE), (1.001, NO_TRAVEL),
])
def test_rain(inches, level):
    assert rain_level(inches) == level


@pytest.mark.parametrize("inches,level", [
    (0.49, LOW), (0.5, MODERATE), (1.0, HIGH), (2.0, SEVERE), (3.0, SEVERE), (3.01, NO_TRAVEL),
])
def test_snow(inches, level):
    assert snow_level(inches) == level


@pytest.mark.parametrize("mph,lb,level", [
    (55, 0, NO_TRAVEL),          # any load
    (45, 30_000, SEVERE),        # weight rule is strictly greater than
    (45, 30_001, NO_TRAVEL),
    (35, 40_000, HIGH),
    (35, 40_001, SEVERE),
    (44, 80_000, SEVERE),
    (34, 80_000, MODERATE),      # load rules start at 35 mph
])
def test_load_rules(mph, lb, level):
    assert assess(mph, 0, 0, lb)[0] == level


def test_worst_condition_wins_and_is_explained():
    level, reason = assess(10, 0.3, 2.5, 10_000)
    assert level == SEVERE
    assert reason == "Snow 2.50 in/hr"


def test_reason_names_load_when_it_raised_the_level():
    assert assess(47, 0, 0, 35_000) == (NO_TRAVEL, "Wind 47 mph with 35,000 lb load")
    assert assess(10, 0, 0, 35_000) == (LOW, "Within safe limits")
