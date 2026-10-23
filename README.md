# RouteRisk: weather-aware truck routing

React + Django app that helps a truck driver pick the safest route for a trip. Enter origin, destination, departure time and load weight. You get three routes scored against the forecast at the hour the truck actually reaches each checkpoint, plus a 0–48 h weather-risk heatmap of the corridor.

**Live:** https://spotter-assessment-production-abb1.up.railway.app · **Walkthrough:** _add your Loom URL_

## How it works

```
form ──POST /api/plan──▶ geocode (Photon) ─▶ 3 routes (OSRM) ─▶ checkpoints every 10/25/50 mi + ETAs
                                                                  │
          map + cards ◀── rank routes ◀── risk rules ◀── hourly forecast at each ETA (Open-Meteo)
```

| File | Job |
|---|---|
| `backend/planner/risk.py` | The brief's wind / rain / snow / load table, one level per checkpoint, with a plain-English reason |
| `backend/planner/ranking.py` | Per-route miles by level, average risk, and the recommendation order |
| `backend/planner/hos.py` | Hours-of-service stops and the wall-clock time they add |
| `backend/planner/geo.py` | Polyline maths: distance, checkpoints, ETA interpolation, the stretch of road each checkpoint covers |
| `backend/planner/routing.py` | Geocoding, routing, and the fallback that finds a 3rd route |
| `backend/planner/weather.py` | Batched, cached hourly forecasts |
| `backend/planner/plan.py` | Assembles routes, scores and the heatmap into one response |
| `frontend/src/MapView.tsx` | Map, risk-coloured routes, checkpoint popups, heatmap and slider |
| `frontend/src/styles/tokens.css` | Design tokens. Every colour and size comes from here, including the risk scale the map uses |

All three services are free and need **no API keys**.

## Decisions on what the brief leaves open

| Question | Decision |
|---|---|
| "Every 10 / 25 / 50 miles" | The user picks the interval (default 25). Checkpoints sit at the origin, every N miles, and the destination. |
| Values exactly on a boundary | Go to the higher band, e.g. rain 0.25 in/hr is High. Where the brief says `>` it is taken literally: rain 1.00 is Severe and only above 1.00 is No Travel. The same applies to snow above 3.0 and to loads above 30,000 / 40,000 lb. |
| Wind, rain and snow at one checkpoint | The worst of the three. Load rules can only raise the level. |
| Gusts | Not used. The brief says "wind", so scoring uses sustained 10 m wind. |
| No Travel in the ranking | Ranked **first**, ahead of the brief's four criteria. A forbidden route must never beat an allowed one. If every route has No Travel miles, a banner says to delay departure. |
| "Severe miles" | Each checkpoint stands for the road halfway to its neighbours, so every mile is counted exactly once. |
| "Average risk" | Low = 0 … No Travel = 4, weighted by miles. |
| Near-ties | Miles are rounded to 0.1 and average risk to 0.01 before comparing, so float noise falls through to travel time. |
| ETA | From OSRM's per-segment durations, interpolated to each checkpoint and matched to the nearest forecast hour. |
| Driver breaks | ETAs follow FMCSA hours of service for one driver: a 30 min break after 8 h of driving and 10 h off after 11 h. Stops are shown on the map, in the route list and in the truck's status, and the trip time used for ranking includes them. The 14 h on-duty window is always met; weekly 60/70 h limits are outside one trip. |
| Departure | Must be within the next 5 days, so the trip and the 48 h slider stay inside the forecast. Up to 1 h in the past counts as "now". |
| Load | 0–80,000 lb (US federal gross limit). |
| Fewer than 3 routes | OSRM often returns 1–2 on long trips. The rest are found by routing through a point offset sideways from the midpoint. Near-duplicates (>80% shared road) and detours >50% slower are dropped. If 3 still can't be found, the app says so and never invents one. |

## Performance

- **Slider:** runs 0–48 h as the brief asks, or to arrival on longer trips. Every hour ships in the first response. Moving the slider swaps one MapLibre paint expression, so there is no network call and no data re-upload.
- **Weather:** points snap to 0.25° cells (about the resolution of the global model) and are deduped across routes and the heatmap. Route risk always uses 0.25° cells. Only the heatmap coarsens (0.5° or 1°) on coast-to-coast trips to stay under Open-Meteo's per-minute limit. If even the checkpoints wouldn't fit, the app asks for wider spacing instead of losing precision. They are fetched 100 per request in parallel and cached per cell for the hour.
- **Payload:** responses are gzipped (~70 KB for a 1,000-mile trip). Route geometry is thinned to one vertex per ¼ mile.
- **Upstream hiccups:** calls to the free APIs retry twice.

## Run locally

```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cd ../frontend && npm install && npm run build
cd .. && backend/.venv/bin/python backend/manage.py runserver 8000   # serves app + API at :8000
```

For frontend hot reload, run `npm run dev` in `frontend/` too (it proxies `/api` to :8000).

**Tests:** `cd backend && .venv/bin/python -m pytest`. They cover every rule boundary, the load rules, ranking order and tie-breaks, checkpoint spacing and mile attribution, ETA interpolation, input validation, the 3rd-route fallback, and one end-to-end plan with the APIs faked.

## Deploy (Railway)

The `Dockerfile` builds the React app, then runs Django + gunicorn, which serves both. Railway sets `PORT`, and any `*.up.railway.app` domain is accepted. For a custom domain, set `ALLOWED_HOSTS=your.domain` in the service's variables.

1. Push this repo to GitHub.
2. In Railway, choose **New Project → Deploy from GitHub repo** and pick it. Railway finds the `Dockerfile` and builds it.
3. Under **Settings → Networking**, click **Generate Domain**.

## Known limits

- OSRM travel times are for cars; trucks are usually slower, so ETAs are optimistic.
- Photon returns its best match. The cards show which place was used, e.g. "Springfield, Illinois".
- Open-Meteo rate-limits by location count. A burst of new corridors can briefly return "busy"; repeat trips hit the cache.
- Stops are placed exactly where the driving limit runs out. A real driver would pull into the nearest truck stop.
