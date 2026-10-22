from planner.ranking import rank, summarize


def route(no_travel=0, severe=0, high=0, avg=0.0, duration=3600):
    return {"no_travel_mi": no_travel, "severe_mi": severe, "high_mi": high,
            "avg_risk": avg, "duration_s": duration}


def test_summary_counts_miles_per_level_and_weighted_average():
    cps = [{"level": 0, "miles": 10}, {"level": 2, "miles": 20}, {"level": 3, "miles": 5}, {"level": 4, "miles": 5}]
    s = summarize(cps, 3600.4)
    assert (s["no_travel_mi"], s["severe_mi"], s["high_mi"], s["duration_s"]) == (5, 5, 20, 3600)
    assert s["avg_risk"] == round((0 * 10 + 2 * 20 + 3 * 5 + 4 * 5) / 40, 2)


def test_no_travel_beats_everything():
    order, reason = rank([route(no_travel=1, duration=60), route(severe=100, duration=9999)])
    assert order == [1, 0]
    assert reason.startswith("Fewest No Travel miles")


def test_each_criterion_breaks_ties_in_order():
    assert rank([route(severe=2), route(severe=1, high=99)])[0] == [1, 0]
    assert rank([route(high=2), route(high=1, avg=3)])[0] == [1, 0]
    assert rank([route(avg=0.5), route(avg=0.4, duration=99999)])[0] == [1, 0]
    order, reason = rank([route(duration=4000), route(duration=3400)])
    assert order == [1, 0]
    assert reason == "Same risk as the next best route and 10 min faster."


def test_near_tie_is_rounded_away_so_travel_time_decides():
    a = summarize([{"level": 2, "miles": 10.04}], 5000)
    b = summarize([{"level": 2, "miles": 10.01}], 4000)
    assert rank([a, b])[0] == [1, 0]


def test_single_route():
    assert rank([route()]) == ([0], "Only route available.")
