import json
from datetime import datetime, timedelta, timezone

import pytest
from django.test import Client

from planner import routing

LINE = [[-100.0, 40.0 + i / 10] for i in range(21)]


def post(**overrides):
    body = {"origin": "Chicago", "destination": "Denver", "load_lb": 30_000, "interval_mi": 25,
            "departure": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(), **overrides}
    return Client(HTTP_HOST="localhost").post("/api/plan", json.dumps(body), content_type="application/json")


@pytest.mark.parametrize("overrides,message", [
    ({"load_lb": 90_000}, "Load must be between"),
    ({"load_lb": -1}, "Load must be between"),
    ({"interval_mi": 30}, "Checkpoint interval"),
    ({"departure": "2020-01-01T00:00:00+00:00"}, "in the past"),
    ({"departure": (datetime.now(timezone.utc) + timedelta(days=6)).isoformat()}, "within the next 5 days"),
    ({"departure": "2030-01-01T00:00:00"}, "time zone"),
    ({"origin": " "}, "Enter an origin"),
    ({"load_lb": "heavy"}, "Invalid request"),
])
def test_rejects_bad_input(overrides, message):
    resp = post(**overrides)
    assert resp.status_code == 400
    assert message in resp.json()["error"]


def route(coords, hours):
    return {"coords": coords, "seconds": [hours * 3600 / (len(coords) - 1)] * (len(coords) - 1),
            "duration_s": hours * 3600, "roads": []}


def test_fallback_routes_skip_duplicates_and_long_detours(monkeypatch):
    main = route(LINE, 2)
    duplicate = route(LINE, 2.1)
    too_slow = route([[x + 1, y] for x, y in LINE], 3.5)   # > 1.5x the fastest
    good = route([[x - 1, y] for x, y in LINE], 2.5)
    answers = iter([[main], [duplicate, too_slow], [good]])
    monkeypatch.setattr(routing, "_osrm", lambda points, alternatives: next(answers))

    assert routing.get_routes([-100, 40], [-100, 42]) == [main, good]


def test_drop_spurs_removes_out_and_back_detour_on_separate_carriageways():
    # East along lat 40, a 3-mile stub north, back down a parallel road ~50 m away, then on east.
    out = [[-100.0 + i * 0.01, 40.0] for i in range(6)]                 # ~2.6 mi east
    stub = [[-99.95, 40.0 + i * 0.01] for i in range(1, 5)]             # up ~2.8 mi
    back = [[-99.9504, 40.0 + i * 0.01] for i in range(3, -1, -1)]      # down the other carriageway
    on = [[-99.95 + i * 0.01, 40.0] for i in range(1, 4)]
    coords = out + stub + back + on
    route = {"coords": coords, "seconds": [60] * (len(coords) - 1), "duration_s": 60 * (len(coords) - 1), "roads": ["US 1"]}

    result = routing._drop_spurs(route)
    assert result["coords"] == out + on
    assert result["seconds"] == [60] * (len(out + on) - 1)   # the stub's drive time is gone too
    assert result["duration_s"] == 60 * (len(out + on) - 1)
    assert result["roads"] == ["US 1"]


def test_road_names_are_the_two_longest_roads_by_highway_number():
    steps = [
        {"ref": "I 80 Express", "name": "Eisenhower Hwy", "distance": 300},
        {"ref": "I 80", "name": "Eisenhower Hwy", "distance": 500},
        {"ref": "I 76; US 6", "name": "", "distance": 600},
        {"name": "Main Street", "distance": 50},
        {"name": "", "distance": 900},              # unnamed ramps are skipped
    ]
    assert routing._roads([{"steps": steps[:3]}, {"steps": steps[3:]}]) == ["I 80", "I 76", "Main Street"]


def test_label_prefers_a_road_the_other_routes_do_not_use():
    assert routing.label(["I 80", "I 76", "US 20"], [["I 80", "I 76"]]) == "I 80, US 20"
    assert routing.label(["I 80", "I 76"], [["I 80", "I 76", "US 20"]]) == "I 80, I 76"
    assert routing.label(["Main Street"], []) == "Main Street"
    assert routing.label([], []) == ""


@pytest.mark.parametrize("host", ["routerisk-production.up.railway.app", "localhost"])
def test_api_answers_json_on_deployed_hosts(host):
    resp = Client(HTTP_HOST=host).post("/api/plan", "{}", content_type="application/json")
    assert resp.status_code == 400
    assert resp.json() == {"error": "Invalid request."}
