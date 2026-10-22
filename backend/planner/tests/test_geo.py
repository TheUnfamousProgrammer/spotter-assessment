import pytest

from planner import geo

# Due north along a meridian: 1° of latitude ≈ 69.09 mi.
LINE = [[-100.0, 40.0], [-100.0, 41.0], [-100.0, 42.0]]


def test_cumulative_miles():
    cum = geo.cumulative_miles(LINE)
    assert cum[0] == 0
    assert cum[2] == pytest.approx(138.2, abs=0.2)


def test_checkpoints_every_interval_plus_destination():
    assert geo.checkpoint_miles(60, 25) == [0, 25, 50, 60]
    assert geo.checkpoint_miles(50.3, 25) == [0, 25, 50]       # destination within half a mile of the last one
    assert geo.checkpoint_miles(8, 10) == [0, 8]


def test_every_mile_belongs_to_exactly_one_checkpoint():
    miles = geo.checkpoint_miles(60, 25)
    bounds = geo.stretch_bounds(miles, 60)
    owned = [b - a for a, b in zip(bounds, bounds[1:])]
    assert owned == [12.5, 25, 17.5, 5]
    assert sum(owned) == 60


def test_eta_is_interpolated_from_segment_durations():
    cum = geo.cumulative_miles(LINE)
    seconds = [0, 3600, 3600 + 7200]          # second half is driven twice as slowly
    assert geo.value_at(cum, seconds, cum[1] / 2) == pytest.approx(1800)
    assert geo.value_at(cum, seconds, cum[1] + (cum[2] - cum[1]) / 2) == pytest.approx(7200)


def test_point_at_and_slice():
    cum = geo.cumulative_miles(LINE)
    assert geo.point_at(LINE, cum, cum[1] / 2) == pytest.approx([-100.0, 40.5])
    part = geo.slice_line(LINE, cum, cum[1] / 2, cum[2])
    assert part[0] == pytest.approx([-100.0, 40.5])
    assert part[-1] == pytest.approx([-100.0, 42.0])


def test_offset_is_perpendicular():
    left = geo.offset([-100.0, 40.0], [-100.0, 41.0], 10)
    assert left[1] == pytest.approx(40.0)
    assert left[0] < -100.0
    assert geo.distance_mi([-100.0, 40.0], left) == pytest.approx(10, rel=0.01)
