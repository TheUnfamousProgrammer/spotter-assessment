"""Polyline helpers. Points are [lng, lat] like GeoJSON; distances in miles."""

import bisect
import math

EARTH_RADIUS_MI = 3958.8
MI_PER_DEG_LAT = 69.0


def distance_mi(a, b):
    lng1, lat1, lng2, lat2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 2 * EARTH_RADIUS_MI * math.asin(math.sqrt(h))


def cumulative_miles(coords):
    out = [0.0]
    for a, b in zip(coords, coords[1:]):
        out.append(out[-1] + distance_mi(a, b))
    return out


def _locate(cum, mile):
    i = min(max(bisect.bisect_right(cum, mile) - 1, 0), len(cum) - 2)
    span = cum[i + 1] - cum[i]
    return i, (mile - cum[i]) / span if span else 0.0


def point_at(coords, cum, mile):
    i, t = _locate(cum, mile)
    (x1, y1), (x2, y2) = coords[i], coords[i + 1]
    return [x1 + (x2 - x1) * t, y1 + (y2 - y1) * t]


def value_at(cum, values, mile):
    i, t = _locate(cum, mile)
    return values[i] + (values[i + 1] - values[i]) * t


def checkpoint_miles(total, interval):
    """Origin, every `interval` miles, and the destination."""
    miles = [i * interval for i in range(int(total // interval) + 1)]
    if total - miles[-1] > 0.5:
        miles.append(total)
    return miles


def stretch_bounds(miles, total):
    """Each checkpoint stands for the road halfway to its neighbours, so every mile counts once."""
    return [0.0] + [(a + b) / 2 for a, b in zip(miles, miles[1:])] + [total]


def slice_line(coords, cum, start, end):
    i, _ = _locate(cum, start)
    j, _ = _locate(cum, end)
    return [point_at(coords, cum, start), *coords[i + 1:j + 1], point_at(coords, cum, end)]


def thin(cum, gap_mi):
    """Indices of vertices at least `gap_mi` apart, always keeping both ends."""
    keep = [0]
    for i in range(1, len(cum) - 1):
        if cum[i] - cum[keep[-1]] >= gap_mi:
            keep.append(i)
    keep.append(len(cum) - 1)
    return keep


def offset(point, toward, mi):
    """Move `point` sideways by `mi` miles, perpendicular to the direction of `toward` (left is +)."""
    lng_scale = MI_PER_DEG_LAT * math.cos(math.radians(point[1]))
    dx = (toward[0] - point[0]) * lng_scale
    dy = (toward[1] - point[1]) * MI_PER_DEG_LAT
    norm = math.hypot(dx, dy) or 1.0
    return [point[0] - dy / norm * mi / lng_scale, point[1] + dx / norm * mi / MI_PER_DEG_LAT]


def overlap(a, b, tolerance_mi=2.0):
    """Share of points in `a` lying within `tolerance_mi` of some point in `b`."""
    return sum(any(distance_mi(p, q) <= tolerance_mi for q in b) for p in a) / len(a)
