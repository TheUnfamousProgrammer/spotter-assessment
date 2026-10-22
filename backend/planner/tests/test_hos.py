import pytest

from planner.hos import BREAK_S, REST_S, stops, wall_clock

H = 3600


@pytest.mark.parametrize("drive_h,wall_h", [
    (0, 0), (7, 7),
    (8, 8),            # break starts once 8 h are driven, so it is not yet counted
    (9, 9.5),          # 30 min break taken
    (11, 11.5),        # end of the first shift: break counted, rest not yet
    (12, 22.5),        # 10 h rest taken
    (20, 31),          # second shift past 8 h: second break
])
def test_wall_clock(drive_h, wall_h):
    assert wall_clock(drive_h * H) == wall_h * H


def test_short_trip_has_no_stops():
    assert stops(8 * H) == []


def test_stops_for_a_20_hour_drive():
    assert stops(20 * H) == [
        ("break", 8 * H, 8 * H, BREAK_S),
        ("rest", 11 * H, 11.5 * H, REST_S),
        ("break", 19 * H, 29.5 * H, BREAK_S),
    ]


def test_no_rest_when_arriving_exactly_at_the_limit():
    assert [kind for kind, *_ in stops(11 * H)] == ["break"]
