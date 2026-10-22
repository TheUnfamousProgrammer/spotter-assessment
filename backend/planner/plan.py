"""Routes -> checkpoints with ETAs -> weather -> risk -> ranking, plus the corridor heatmap."""

import math
from datetime import timedelta
from itertools import accumulate

from . import geo, hos, routing, weather
from .ranking import rank, summarize
from .risk import LOW, assess, factor_levels

MIN_SLIDER_HOURS = 48  # the brief's 0-48 h; longer trips extend it to arrival
HEATMAP_SPACING_MI = 30
HEATMAP_OFFSETS_MI = (-30, 0, 30)
DRAW_GAP_MI = 0.25  # route geometry sent to the browser keeps one vertex per quarter mile
TRACK_GAP_MI = 1.0  # the truck marker's timed path: one point per mile


def build_plan(origin, destination, departure, load_lb, interval_mi):
    start = departure.replace(minute=0, second=0, microsecond=0)
    lead_s = (departure - start).total_seconds()

    raw_routes = routing.get_routes([origin["lng"], origin["lat"]], [destination["lng"], destination["lat"]])
    routes = [_prepare(r, interval_mi, routing.label(r["roads"], [o["roads"] for o in raw_routes if o is not r]))
              for r in raw_routes]
    # Route risk always uses full-detail cells; the heatmap gets whatever rate-limit budget is left.
    checkpoint_cells = {weather.grid_key(cp["point"]) for r in routes for cp in r["checkpoints"]}
    if len(checkpoint_cells) > weather.MAX_CELLS:
        raise routing.PlanError("This trip needs too many weather checks at this spacing. Try 25 or 50 miles.")
    cell, heat_cells = _heat_cells(checkpoint_cells, _corridor(routes))

    last_eta_s = max(r["checkpoints"][-1]["eta_s"] for r in routes)
    slider_hours = max(MIN_SLIDER_HOURS, math.ceil((lead_s + last_eta_s) / 3600))
    hours = slider_hours + 1
    forecast = weather.fetch(checkpoint_cells | heat_cells, start, hours)

    results = [_score(r, forecast, departure, lead_s, load_lb) for r in routes]
    order, reason = rank([r["summary"] for r in results])
    results = [results[i] for i in order]
    notes = [] if len(results) == routing.WANTED_ROUTES else [
        f"Only {len(results)} distinct route{'s' if len(results) > 1 else ''} found for this trip."]

    return {
        "origin": origin,
        "destination": destination,
        "departure": departure.isoformat(),
        "forecast_start": start.isoformat(),
        "slider_hours": slider_hours,
        "heatmap_cell_deg": cell,
        "routes": results,
        "reason": reason,
        "all_no_travel": all(r["summary"]["no_travel_mi"] > 0 for r in results),
        "notes": notes,
        "heatmap": {"type": "FeatureCollection", "features": [{
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {f"h{h}": assess(*forecast[(lat, lng)][h], load_lb)[0] for h in range(hours)},
        } for lat, lng in heat_cells]},
    }


def _prepare(raw, interval_mi, via):
    """Times here are after departure and include hours-of-service stops; `drive_s` is wheels-turning time only."""
    coords = raw["coords"]
    cum_mi = geo.cumulative_miles(coords)
    drive_s = [0.0, *accumulate(raw["seconds"])]
    miles = geo.checkpoint_miles(cum_mi[-1], interval_mi)
    bounds = geo.stretch_bounds(miles, cum_mi[-1])
    stops = []
    for kind, at_drive_s, start_s, length_s in hos.stops(drive_s[-1]):
        mile = geo.value_at(drive_s, cum_mi, at_drive_s)
        stops.append({"kind": kind, "mile": mile, "point": geo.point_at(coords, cum_mi, mile),
                      "start_s": start_s, "length_s": length_s})
    return {
        "coords": coords,
        "via": via,
        "cum": cum_mi,
        "drive_s": drive_s,
        "duration_s": hos.wall_clock(drive_s[-1]),
        "stops": stops,
        "bounds": bounds,
        "checkpoints": [{
            "mile": m,
            "point": geo.point_at(coords, cum_mi, m),
            "eta_s": hos.wall_clock(geo.value_at(cum_mi, drive_s, m)),
            "miles": bounds[i + 1] - bounds[i],
        } for i, m in enumerate(miles)],
    }


def _score(route, forecast, departure, lead_s, load_lb):
    checkpoints = []
    for cp in route["checkpoints"]:
        hour = round((lead_s + cp["eta_s"]) / 3600)
        wind, rain, snow = forecast[weather.grid_key(cp["point"])][hour]
        level, reason = assess(wind, rain, snow, load_lb)
        checkpoints.append({
            "mile": round(cp["mile"], 1),
            "lng": round(cp["point"][0], 5),
            "lat": round(cp["point"][1], 5),
            "eta": (departure + timedelta(seconds=round(cp["eta_s"]))).isoformat(),
            "wind": round(wind, 1),
            "rain": rain,
            "snow": snow,
            "level": level,
            "factors": factor_levels(wind, rain, snow, load_lb),
            "reason": reason,
            "miles": cp["miles"],
        })

    keep = geo.thin(route["cum"], DRAW_GAP_MI)
    coords, cum = [route["coords"][i] for i in keep], [route["cum"][i] for i in keep]
    bounds = route["bounds"]

    # [lng, lat, seconds after departure] for placing the truck at any time; it stands still during stops.
    track = [[*_round_point(route["coords"][i]), round(hos.wall_clock(route["drive_s"][i]))]
             for i in geo.thin(route["cum"], TRACK_GAP_MI)]
    for stop in route["stops"]:
        point = _round_point(stop["point"])
        track += [[*point, round(stop["start_s"])], [*point, round(stop["start_s"] + stop["length_s"])]]
    track.sort(key=lambda p: p[2])

    return {
        "via": route["via"],
        "distance_mi": round(route["cum"][-1], 1),
        "drive_s": round(route["drive_s"][-1]),
        "stops": [{
            "kind": stop["kind"],
            "mile": round(stop["mile"], 1),
            "lng": round(stop["point"][0], 5),
            "lat": round(stop["point"][1], 5),
            "start": (departure + timedelta(seconds=round(stop["start_s"]))).isoformat(),
            "end": (departure + timedelta(seconds=round(stop["start_s"] + stop["length_s"]))).isoformat(),
        } for stop in route["stops"]],
        "summary": summarize(checkpoints, route["duration_s"]),
        "hazards": _hazards(checkpoints, bounds),
        "checkpoints": checkpoints,
        "track": track,
        "segments": [{"level": cp["level"], "coords": _round_line(geo.slice_line(coords, cum, bounds[i], bounds[i + 1]))}
                     for i, cp in enumerate(checkpoints)],
    }


def _hazards(checkpoints, bounds):
    """Stretches of road at Moderate or worse; neighbouring checkpoints at the same level merge."""
    hazards, current = [], None
    for i, cp in enumerate(checkpoints):
        if cp["level"] == LOW:
            current = None
        elif current and current["level"] == cp["level"]:
            current["to_mi"] = round(bounds[i + 1], 1)
        else:
            current = {"level": cp["level"], "from_mi": round(bounds[i], 1), "to_mi": round(bounds[i + 1], 1),
                       "reason": cp["reason"], "eta": cp["eta"], "lng": cp["lng"], "lat": cp["lat"]}
            hazards.append(current)
    return hazards


def _round_point(point):
    return [round(point[0], 5), round(point[1], 5)]


def _round_line(line):
    return [_round_point(p) for p in line]


def _heat_cells(checkpoint_cells, corridor):
    """(cell size, cells) for the heatmap: the finest grid over the corridor that fits the
    budget left after the checkpoints. If none fits, the cells along the routes themselves."""
    for size in weather.CELL_SIZES:
        cells = {weather.grid_key(p, size) for p in corridor}
        if len(checkpoint_cells | cells) <= weather.MAX_CELLS:
            return size, cells
    return weather.CELL_SIZES[0], checkpoint_cells


def _corridor(routes):
    """Points along and to both sides of every route, for the heatmap."""
    points = []
    for r in routes:
        coords, cum = r["coords"], r["cum"]
        for m in range(0, int(cum[-1]) + 1, HEATMAP_SPACING_MI):
            here, ahead = geo.point_at(coords, cum, m), geo.point_at(coords, cum, m + 1)
            for off in HEATMAP_OFFSETS_MI:
                points.append(geo.offset(here, ahead, off))
    return points
