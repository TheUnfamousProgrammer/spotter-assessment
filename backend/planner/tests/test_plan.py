"""build_plan end to end with the routing and weather services faked."""

from datetime import datetime, timezone

import pytest

from planner import plan, routing, weather
from planner.risk import LOW, NO_TRAVEL

DEPARTURE = datetime(2026, 1, 1, 8, 20, tzinfo=timezone.utc)
ORIGIN = {"label": "A", "lng": -100.0, "lat": 40.0}
DEST = {"label": "B", "lng": -100.0, "lat": 42.0}


def fake_route(lng, hours):
    """A straight 138-mile route north along `lng`, driven in `hours`."""
    coords = [[lng, 40.0 + i / 100] for i in range(201)]
    return {"coords": coords, "seconds": [hours * 3600 / 200] * 200, "duration_s": hours * 3600, "roads": ["I 1", "Test Rd"]}


def test_plan_scores_checkpoints_at_arrival_hour_and_ranks(monkeypatch):
    fast_stormy, slow_calm = fake_route(-100.0, 2), fake_route(-101.0, 4)
    monkeypatch.setattr(routing, "get_routes", lambda a, b: [fast_stormy, slow_calm])

    def fake_fetch(keys, start, hours):
        assert start == datetime(2026, 1, 1, 8, tzinfo=timezone.utc)
        out = {}
        for lat, lng in keys:
            # 50 mph wind on the -100 corridor, but only from 09:00 on.
            wind = [50.0 if lng == -100.0 and h >= 1 else 5.0 for h in range(hours)]
            out[(lat, lng)] = [(w, 0.0, 0.0) for w in wind]
        return out
    monkeypatch.setattr(weather, "fetch", fake_fetch)

    result = plan.build_plan(ORIGIN, DEST, DEPARTURE, 35_000, 25)
    assert result["slider_hours"] == 48             # short trip: the brief's 0-48 h

    calm, stormy = result["routes"]                  # best first
    assert calm["summary"]["no_travel_mi"] == 0
    assert result["reason"].startswith("Fewest No Travel miles")
    assert result["notes"] == ["Only 2 distinct routes found for this trip."]

    # Departure 08:20 reads the 08:00 forecast (calm); mile 25 is reached ~08:42, so it reads 09:00.
    # 50 mph with 35,000 lb (> 30,000) is No Travel.
    levels = [cp["level"] for cp in stormy["checkpoints"]]
    assert levels[0] == LOW
    assert set(levels[1:]) == {NO_TRAVEL}
    assert stormy["checkpoints"][1]["eta"] == "2026-01-01T08:41:43+00:00"
    assert len(stormy["segments"]) == len(stormy["checkpoints"])
    assert stormy["checkpoints"][1]["factors"] == {"wind": NO_TRAVEL, "rain": LOW, "snow": LOW}
    assert stormy["via"] == "I 1, Test Rd"
    track = stormy["track"]
    assert track[0] == [-100.0, 40.0, 0] and track[-1] == [-100.0, 42.0, 7200]
    assert all(a[2] < b[2] for a, b in zip(track, track[1:]))

    # One merged No Travel stretch from halfway to the first checkpoint through the destination.
    [hazard] = stormy["hazards"]
    assert (hazard["level"], hazard["from_mi"], hazard["to_mi"]) == (NO_TRAVEL, 12.5, stormy["distance_mi"])
    assert hazard["reason"] == "Wind 50 mph with 35,000 lb load"
    assert calm["hazards"] == []

    on_route = [f["properties"] for f in result["heatmap"]["features"] if f["geometry"]["coordinates"][0] == -100.0]
    assert on_route and all(p["h0"] == LOW and p["h1"] == NO_TRAVEL and "h48" in p for p in on_route)


def test_long_trip_includes_hours_of_service_stops(monkeypatch):
    long_haul = fake_route(-100.0, 20)                           # 20 h of driving
    monkeypatch.setattr(routing, "get_routes", lambda a, b: [long_haul])
    monkeypatch.setattr(weather, "fetch", lambda keys, start, hours: {k: [(5.0, 0.0, 0.0)] * hours for k in keys})

    result = plan.build_plan(ORIGIN, DEST, DEPARTURE, 35_000, 25)
    [route] = result["routes"]

    # 20 h driving + 30 min break + 10 h rest + 30 min break.
    assert route["drive_s"] == 20 * 3600
    assert route["summary"]["duration_s"] == 31 * 3600
    # Still under 48 h, so the slider keeps the brief's range.
    assert result["slider_hours"] == 48
    assert route["checkpoints"][-1]["eta"] == "2026-01-02T15:20:00+00:00"
    assert [(s["kind"], s["start"], s["end"]) for s in route["stops"]] == [
        ("break", "2026-01-01T16:20:00+00:00", "2026-01-01T16:50:00+00:00"),
        ("rest", "2026-01-01T19:50:00+00:00", "2026-01-02T05:50:00+00:00"),
        ("break", "2026-01-02T13:50:00+00:00", "2026-01-02T14:20:00+00:00"),
    ]
    # The truck stands still through the rest: same place at its start and its end, 10 h apart.
    rest = [p for p in route["track"] if p[2] in (11.5 * 3600, 21.5 * 3600)]
    assert {p[2] for p in rest} == {11.5 * 3600, 21.5 * 3600}
    assert len({tuple(p[:2]) for p in rest}) == 1


def test_slider_extends_to_arrival_on_trips_longer_than_48_hours(monkeypatch):
    monkeypatch.setattr(routing, "get_routes", lambda a, b: [fake_route(-100.0, 45)])    # 45 h driving
    monkeypatch.setattr(weather, "fetch", lambda keys, start, hours: {k: [(5.0, 0.0, 0.0)] * hours for k in keys})

    result = plan.build_plan(ORIGIN, DEST, DEPARTURE, 35_000, 25)

    # 45 h driving + 4 rests + 4 breaks (the last 1 h shift needs none) = 87 h; +20 min lead -> 88 h.
    assert result["slider_hours"] == 88
    assert {f"h{h}" for h in range(89)} == set(result["heatmap"]["features"][0]["properties"])


@pytest.mark.parametrize("max_cells,heat_deg,fetched", [
    (100, 0.25, 19),   # plenty of budget: everything at full detail
    (17, 0.5, 17),     # the heatmap coarsens to fit
    (10, 0.25, 9),     # no room for a corridor: heat along the route's own cells
])
def test_checkpoints_keep_full_detail_and_the_heatmap_takes_what_is_left(monkeypatch, max_cells, heat_deg, fetched):
    # This 138-mile route at 10-mile spacing has 9 checkpoint cells; the corridor adds 10 / 8 / 6 at 0.25° / 0.5° / 1°.
    monkeypatch.setattr(weather, "MAX_CELLS", max_cells)
    seen = {}

    def fake_fetch(keys, start, hours):
        seen["keys"] = keys
        return {k: [(5.0, 0.0, 0.0)] * hours for k in keys}
    monkeypatch.setattr(routing, "get_routes", lambda a, b: [fake_route(-100.0, 2)])
    monkeypatch.setattr(weather, "fetch", fake_fetch)

    result = plan.build_plan(ORIGIN, DEST, DEPARTURE, 35_000, 10)

    assert result["heatmap_cell_deg"] == heat_deg
    assert len(seen["keys"]) == fetched
    checkpoint_cells = {weather.grid_key([c["lng"], c["lat"]]) for c in result["routes"][0]["checkpoints"]}
    assert checkpoint_cells <= seen["keys"]


def test_too_many_checkpoint_cells_asks_for_wider_spacing(monkeypatch):
    monkeypatch.setattr(weather, "MAX_CELLS", 8)
    monkeypatch.setattr(routing, "get_routes", lambda a, b: [fake_route(-100.0, 2)])
    with pytest.raises(routing.PlanError, match="Try 25 or 50 miles"):
        plan.build_plan(ORIGIN, DEST, DEPARTURE, 35_000, 10)
