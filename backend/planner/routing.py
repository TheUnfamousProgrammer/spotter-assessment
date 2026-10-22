"""Geocoding (Photon) and routing (OSRM). Both are free and need no API key."""

import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from itertools import accumulate

from . import geo
from .http import TIMEOUT, session

OSRM_URL = "https://router.project-osrm.org/route/v1/driving/"
PHOTON_URL = "https://photon.komoot.io/api/"
WANTED_ROUTES = 3
DETOUR_SHARE = 0.15      # via-point offset, as a share of the trip length
MAX_SLOWDOWN = 1.5       # an alternative may take at most 50% longer than the fastest
MAX_OVERLAP = 0.8        # alternatives sharing more road than this count as duplicates
SPUR_MIN_MI = 1.0        # a return to a point passed this far back counts as doubling back


class PlanError(Exception):
    """A problem the user can act on (place not found, no road route)."""


def geocode(query):
    # Biased toward the continental US, where mph/lb rules apply.
    resp = session.get(PHOTON_URL, params={"q": query, "limit": 1, "lat": 39.8, "lon": -98.6}, timeout=TIMEOUT)
    resp.raise_for_status()
    features = resp.json()["features"]
    if not features:
        raise PlanError(f'Could not find "{query}".')
    props = features[0]["properties"]
    label = ", ".join(dict.fromkeys(p for p in (props.get("name"), props.get("state"), props.get("countrycode")) if p))
    lng, lat = features[0]["geometry"]["coordinates"]
    return {"label": label, "lng": lng, "lat": lat}


def _osrm(points, alternatives):
    path = ";".join(f"{lng},{lat}" for lng, lat in points)
    resp = session.get(OSRM_URL + path, timeout=TIMEOUT, params={
        "alternatives": WANTED_ROUTES if alternatives else "false",
        "overview": "full", "geometries": "geojson", "annotations": "duration",
        "steps": "true",  # only for the road names in _road_names
    })
    if resp.status_code == 429 or resp.status_code >= 500:
        resp.raise_for_status()
    data = resp.json()
    if data.get("code") != "Ok":
        return []
    # With overview=full, per-leg annotations line up with the geometry's segments.
    return [{
        "coords": r["geometry"]["coordinates"],
        "seconds": [s for leg in r["legs"] for s in leg["annotation"]["duration"]],
        "duration_s": r["duration"],
        "roads": _roads(r["legs"]),
    } for r in data["routes"]]


def _roads(legs):
    """Roads driven longest first, as highway numbers where they have one: ["I 80", "I 76", ...]."""
    meters = Counter()
    for step in (s for leg in legs for s in leg["steps"]):
        number = re.match(r"[A-Z]+ \d+", step.get("ref", ""))  # "I 80 Express; US 6" -> "I 80"
        road = number.group() if number else step["name"]
        if road:
            meters[road] += step["distance"]
    return [road for road, _ in meters.most_common(8)]


def label(roads, other_routes):
    """Main road plus the longest road no other route uses, so similar routes still read differently."""
    others = {road for roads_ in other_routes for road in roads_}
    second = next((road for road in roads[1:] if road not in others), roads[1] if len(roads) > 1 else None)
    return ", ".join(filter(None, [roads[0] if roads else None, second]))


def get_routes(origin, destination):
    """Up to 3 distinct routes. OSRM often returns only 1-2 on long trips, so the rest
    are found by forcing the route through a point offset to either side of the midpoint."""
    routes = _osrm([origin, destination], alternatives=True)
    if not routes:
        raise PlanError("No drivable route found between these places.")
    main = routes[0]["coords"]
    cum = geo.cumulative_miles(main)
    mid, ahead = geo.point_at(main, cum, cum[-1] / 2), geo.point_at(main, cum, cum[-1] / 2 + 5)
    if len(routes) < WANTED_ROUTES:
        vias = [geo.offset(mid, ahead, side * DETOUR_SHARE * cum[-1]) for side in (1, -1)]
        with ThreadPoolExecutor(max_workers=2) as pool:
            detours = pool.map(lambda via: _osrm([origin, via, destination], alternatives=False), vias)
        for cand in (_drop_spurs(r) for found in detours for r in found):
            if cand["duration_s"] <= MAX_SLOWDOWN * routes[0]["duration_s"] and all(
                geo.overlap(_sample(cand), _sample(r)) < MAX_OVERLAP for r in routes
            ):
                routes.append(cand)
    return routes[:WANTED_ROUTES]


def _drop_spurs(route):
    """Remove the out-and-back stub a via point can cause. Coming back within ~100 m of a
    point passed more than a mile earlier means the path doubled back: cut everything in
    between, including its drive time. Tolerance, not exact match, because divided
    highways run out and back on separate carriageways."""
    cum_mi = geo.cumulative_miles(route["coords"])
    cum_s = [0.0, *accumulate(route["seconds"])]
    kept, seen, removed_s = [], {}, 0.0   # kept: (index, adjusted time, cell); seen: cell -> position in kept
    for i, (lng, lat) in enumerate(route["coords"]):
        cell = (round(lng, 3), round(lat, 3))
        j = seen.get(cell)
        if j is not None and cum_mi[i] - cum_mi[kept[j][0]] > SPUR_MIN_MI:
            removed_s = cum_s[i] - kept[j][1]
            for _, _, dropped in kept[j + 1:]:
                if seen.get(dropped, -1) > j:
                    del seen[dropped]
            del kept[j + 1:]
            continue
        seen.setdefault(cell, len(kept))
        kept.append((i, cum_s[i] - removed_s, cell))
    times = [t for _, t, _ in kept]
    return {
        "coords": [route["coords"][i] for i, _, _ in kept],
        "seconds": [b - a for a, b in zip(times, times[1:])],
        "duration_s": times[-1],
        "roads": route["roads"],
    }


def _sample(route):
    coords = route["coords"]
    return [coords[i] for i in geo.thin(geo.cumulative_miles(coords), 5)]
