"""Hourly forecasts from Open-Meteo (free, no key), many points per request.

Open-Meteo rate-limits per location (~600 a minute), so points share grid cells and each
cell's forecast is cached for the hour. Cells are 0.25°, about the resolution of its global
model; only the heatmap may use coarser cells (see plan._heat_cells).
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from django.core.cache import cache

from .http import TIMEOUT, session

URL = "https://api.open-meteo.com/v1/forecast"
BATCH = 100
CELL_SIZES = (0.25, 0.5, 1.0)  # degrees, finest first
MAX_CELLS = 550  # per plan, under the per-minute limit
WINDOW_H = 240  # 5-day departure limit + longest trip + 48 h slider


def grid_key(point, size=CELL_SIZES[0]):
    """Snap [lng, lat] to a `size`-degree cell; returns (lat, lng) of the cell centre."""
    return round(round(point[1] / size) * size, 4), round(round(point[0] / size) * size, 4)


def fetch(keys, start, hours):
    """Return {key: [(wind_mph, rain_in_hr, snow_in_hr), ...]} for `hours` hours from `start` (UTC, on the hour)."""
    # min(): the request may have crossed into a new hour since `start` was set.
    now_hour = min(start, datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0))
    names = {key: f"wx:{now_hour:%Y%m%d%H}:{key[0]}:{key[1]}" for key in keys}
    cached = cache.get_many(names.values())
    series = {key: cached[name] for key, name in names.items() if name in cached}

    missing = [key for key in names if key not in series]
    chunks = [missing[i:i + BATCH] for i in range(0, len(missing), BATCH)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for chunk, locations in zip(chunks, pool.map(lambda c: _request(c, now_hour), chunks)):
            for key, loc in zip(chunk, locations):
                h = loc["hourly"]
                # shortcut: a missing hour reads as calm; departure is capped at 5 days so all hours are in range.
                series[key] = [(w or 0.0, r or 0.0, s or 0.0)
                               for w, r, s in zip(h["wind_speed_10m"], h["rain"], h["snowfall"])]
    cache.set_many({names[key]: series[key] for key in missing}, timeout=3600)

    offset = int((start - now_hour).total_seconds() // 3600)
    return {key: s[offset:offset + hours] for key, s in series.items()}


def _request(chunk, now_hour):
    resp = session.get(URL, timeout=TIMEOUT, params={
        "latitude": ",".join(str(lat) for lat, _ in chunk),
        "longitude": ",".join(str(lng) for _, lng in chunk),
        "hourly": "wind_speed_10m,rain,snowfall",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "timezone": "GMT",
        "start_hour": now_hour.strftime("%Y-%m-%dT%H:%M"),
        "end_hour": (now_hour + timedelta(hours=WINDOW_H - 1)).strftime("%Y-%m-%dT%H:%M"),
    })
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else [data]
