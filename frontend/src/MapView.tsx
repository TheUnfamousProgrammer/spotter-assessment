import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import Map, { Layer, Marker, NavigationControl, Popup, Source, type MapLayerMouseEvent, type MapRef } from 'react-map-gl/maplibre'
import type { ExpressionSpecification } from 'maplibre-gl'
import type { FeatureCollection, LineString, Point } from 'geojson'
import { dateTime, duration, LEVELS, riskColor, STOP_LABELS } from './format'
import { RiskLegend } from './RiskLegend'
import type { Plan, Route } from './types'

const STYLE = 'https://tiles.openfreemap.org/styles/liberty'
const HOUR = 3_600_000
const FIT_PADDING = { top: 60, bottom: 200, left: 60, right: 60 }
const SLIDER_STEP_H = 1 / 60 // one minute, so dragging moves the truck smoothly
const PLAY_SECONDS = 15 // playing the whole slider range takes this long, whatever the trip length

/** Where the truck is `seconds` after departure: interpolated along the route's timed track. */
function truckAt(track: Route['track'], seconds: number): [number, number] {
  const i = track.findIndex((p) => p[2] >= seconds)
  if (i <= 0) {
    const [lng, lat] = i === 0 ? track[0] : track[track.length - 1] // before departure / after arrival
    return [lng, lat]
  }
  const [x1, y1, t1] = track[i - 1]
  const [x2, y2, t2] = track[i]
  const f = (seconds - t1) / (t2 - t1)
  return [x1 + (x2 - x1) * f, y1 + (y2 - y1) * f]
}

export function MapView({ plan, selected, onSelect }: { plan: Plan | null; selected: number; onSelect: (i: number) => void }) {
  const mapRef = useRef<MapRef>(null)
  const [hour, setHour] = useState(0)
  const [playing, setPlaying] = useState(false)
  const hourRef = useRef(hour) // the animation reads the latest hour without restarting each frame
  hourRef.current = hour
  const [popup, setPopup] = useState<{ route: number; index: number } | null>(null)
  const [cursor, setCursor] = useState('')

  // MapLibre paints with real colors, so read them from the design tokens.
  const { risk, altRoute } = useMemo(() => {
    const css = getComputedStyle(document.documentElement)
    return {
      risk: LEVELS.map((_, i) => css.getPropertyValue(`--risk-${i}`).trim()),
      altRoute: css.getPropertyValue('--route-alt').trim(),
    }
  }, [])
  const byLevel: ExpressionSpecification = ['match', ['get', 'level'], 0, risk[0], 1, risk[1], 2, risk[2], 3, risk[3], risk[4]]
  const isSelected: ExpressionSpecification = ['==', ['get', 'route'], selected]

  const lines = useMemo<FeatureCollection<LineString>>(() => ({
    type: 'FeatureCollection',
    features: (plan?.routes ?? []).flatMap((r, route) =>
      r.segments.map((s) => ({
        type: 'Feature',
        properties: { route, level: s.level },
        geometry: { type: 'LineString', coordinates: s.coords },
      })),
    ),
  }), [plan])

  const points = useMemo<FeatureCollection<Point>>(() => ({
    type: 'FeatureCollection',
    features: (plan?.routes ?? []).flatMap((r, route) =>
      r.checkpoints.map((c, index) => ({
        type: 'Feature',
        properties: { route, index, level: c.level },
        geometry: { type: 'Point', coordinates: [c.lng, c.lat] },
      })),
    ),
  }), [plan])

  useEffect(() => {
    setPopup(null)
    setHour(0)
    setPlaying(false)
  }, [plan])

  useEffect(() => {
    if (!playing || !plan) return
    // Advance by real elapsed time each frame, so the truck glides instead of jumping.
    const hoursPerMs = plan.slider_hours / (PLAY_SECONDS * 1000)
    let frame = 0
    let last = performance.now()
    const tick = (now: number) => {
      const next = Math.min(hourRef.current + (now - last) * hoursPerMs, plan.slider_hours)
      last = now
      setHour(next)
      if (next < plan.slider_hours) frame = requestAnimationFrame(tick)
      else setPlaying(false)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [playing, plan])

  useEffect(() => {
    const coords = plan?.routes[selected]?.segments.flatMap((s) => s.coords)
    if (!coords?.length) return
    const lngs = coords.map((c) => c[0])
    const lats = coords.map((c) => c[1])
    mapRef.current?.fitBounds(
      [[Math.min(...lngs), Math.min(...lats)], [Math.max(...lngs), Math.max(...lats)]],
      { padding: FIT_PADDING, duration: 700 },
    )
  }, [plan, selected])

  function handleClick(e: MapLayerMouseEvent) {
    const feature = e.features?.[0]
    if (!feature) return setPopup(null)
    const { route, index } = feature.properties as { route: number; index?: number }
    onSelect(route)
    setPopup(feature.layer.id === 'checkpoints' ? { route, index: index! } : null)
  }

  const cp = popup && plan?.routes[popup.route].checkpoints[popup.index]
  const route = plan?.routes[selected]
  const elapsed = plan ? (Date.parse(plan.forecast_start) + hour * HOUR - Date.parse(plan.departure)) / 1000 : 0
  const truck = route && truckAt(route.track, elapsed)
  const now = plan ? Date.parse(plan.forecast_start) + hour * HOUR : 0
  const stop = route?.stops.find((s) => Date.parse(s.start) <= now && now < Date.parse(s.end))
  const truckStatus = !route ? '' : elapsed < 0 ? `Departs ${dateTime(plan!.departure)}`
    : elapsed >= route.summary.duration_s ? 'Arrived'
    : stop ? `${STOP_LABELS[stop.kind]} at mile ${stop.mile}, back on the road ${dateTime(stop.end)}`
    : `${duration(elapsed)} on the road`

  return (
    <div className="map-wrap">
      <Map
        ref={mapRef}
        mapStyle={STYLE}
        initialViewState={{ longitude: -96, latitude: 38.5, zoom: 3.6 }}
        interactiveLayerIds={plan ? ['checkpoints', 'routes-selected', 'routes-other'] : []}
        cursor={cursor}
        onMouseEnter={() => setCursor('pointer')}
        onMouseLeave={() => setCursor('')}
        onClick={handleClick}
      >
        <NavigationControl position="top-right" showCompass={false} />
        {plan && (
          <>
            <Source id="heat" type="geojson" data={plan.heatmap}>
              <Layer
                id="heat"
                type="heatmap"
                paint={{
                  // Only this expression changes with the slider: no refetch, no new data upload.
                  'heatmap-weight': ['/', ['get', `h${Math.round(hour)}`], 4],
                  // Grows with zoom and with cell size (0.25° ≈ 17 mi; long trips use coarser cells) so cells blend.
                  'heatmap-radius': ['interpolate', ['exponential', 2], ['zoom'],
                    3, 18 * plan.heatmap_cell_deg, 10, 2304 * plan.heatmap_cell_deg],
                  'heatmap-opacity': 0.8,
                  // A lone cell's density is about its weight (level / 4), so stops sit just under each level.
                  'heatmap-color': [
                    'interpolate', ['linear'], ['heatmap-density'],
                    0, 'rgba(0,0,0,0)', 0.08, 'rgba(0,0,0,0)', 0.2, risk[1], 0.45, risk[2], 0.7, risk[3], 0.95, risk[4],
                  ],
                }}
              />
            </Source>
            <Source id="routes" type="geojson" data={lines}>
              <Layer
                id="routes-other"
                type="line"
                filter={['!', isSelected]}
                layout={{ 'line-cap': 'round', 'line-join': 'round' }}
                paint={{ 'line-color': altRoute, 'line-width': 5, 'line-opacity': 0.8 }}
              />
              <Layer
                id="routes-casing"
                type="line"
                filter={isSelected}
                layout={{ 'line-cap': 'round', 'line-join': 'round' }}
                paint={{ 'line-color': '#ffffff', 'line-width': 10 }}
              />
              <Layer
                id="routes-selected"
                type="line"
                filter={isSelected}
                layout={{ 'line-cap': 'round', 'line-join': 'round' }}
                paint={{ 'line-color': byLevel, 'line-width': 6 }}
              />
            </Source>
            <Source id="checkpoints" type="geojson" data={points}>
              <Layer
                id="checkpoints"
                type="circle"
                layout={{ 'circle-sort-key': ['case', isSelected, 1, 0] }}
                paint={{
                  'circle-color': byLevel,
                  'circle-radius': ['case', isSelected, 6, 3.5],
                  'circle-stroke-color': '#ffffff',
                  'circle-stroke-width': ['case', isSelected, 2, 1],
                }}
              />
            </Source>
            <Marker longitude={plan.origin.lng} latitude={plan.origin.lat}>
              <span className="marker-start" title={plan.origin.label} />
            </Marker>
            <Marker longitude={plan.destination.lng} latitude={plan.destination.lat} anchor="bottom">
              <span className="marker-end" title={plan.destination.label} />
            </Marker>
            {plan.routes.map((r, i) => {
              // Stagger the bubbles along each route so they rarely sit on top of each other.
              const line = r.segments.flatMap((s) => s.coords)
              const [lng, lat] = line[Math.floor((line.length - 1) * (0.35 + 0.15 * i))]
              return (
                <Marker key={i} longitude={lng} latitude={lat} anchor="bottom" style={{ zIndex: i === selected ? 2 : 1 }}>
                  <button
                    type="button"
                    className={`bubble${i === selected ? ' selected' : ''}`}
                    onClick={(e) => {
                      e.stopPropagation()
                      onSelect(i)
                    }}
                  >
                    {duration(r.summary.duration_s)}
                  </button>
                </Marker>
              )
            })}
            {route?.stops.map((s) => (
              <Marker key={s.start} longitude={s.lng} latitude={s.lat} style={{ zIndex: 2 }}>
                <span
                  className="stop-marker"
                  role="img"
                  aria-label={`${STOP_LABELS[s.kind]}, mile ${s.mile}, ${dateTime(s.start)}`}
                  title={`${STOP_LABELS[s.kind]} · mile ${s.mile} · ${dateTime(s.start)} – ${dateTime(s.end)}`}
                >
                  {s.kind === 'rest' ? '🛏' : '☕'}
                </span>
              </Marker>
            ))}
            {truck && (
              <Marker longitude={truck[0]} latitude={truck[1]} style={{ zIndex: 3 }}>
                <span className="truck" role="img" aria-label={`Truck: ${truckStatus}`} title={truckStatus}>
                  <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
                    <path fill="currentColor" d="M2 6h11v9H2zM14 9h4l3 3v3h-7zM6.5 19a2 2 0 1 1 0-4 2 2 0 0 1 0 4zm11 0a2 2 0 1 1 0-4 2 2 0 0 1 0 4z" />
                  </svg>
                </span>
              </Marker>
            )}
          </>
        )}
        {cp && (
          <Popup longitude={cp.lng} latitude={cp.lat} closeOnClick={false} onClose={() => setPopup(null)} maxWidth="260px">
            <div className="cp-popup">
              <span className="chip" style={{ '--risk': riskColor(cp.level) } as CSSProperties}>{LEVELS[cp.level]}</span>
              <p className="muted">Mile {cp.mile} · arrives <strong>{dateTime(cp.eta)}</strong></p>
              <dl className="cp-weather num">
                {([['Wind', `${cp.wind} mph`, cp.factors.wind], ['Rain', `${cp.rain.toFixed(2)} in/hr`, cp.factors.rain],
                  ['Snow', `${cp.snow.toFixed(2)} in/hr`, cp.factors.snow]] as const).map(([name, value, level]) => (
                  <div key={name} style={{ '--risk': riskColor(level) } as CSSProperties}>
                    <dt className="chip">{name}</dt>
                    <dd>{value}</dd>
                    <dd className="muted">{LEVELS[level]}</dd>
                  </div>
                ))}
              </dl>
              <p className="cp-reason">{cp.reason}</p>
            </div>
          </Popup>
        )}
      </Map>

      <RiskLegend />

      {plan && (
        <div className="time-panel card">
          <div className="time-head">
            <span className="eyebrow">Weather heatmap</span>
            <strong className="num">{dateTime(new Date(Date.parse(plan.forecast_start) + hour * HOUR))}</strong>
            <span className="muted num">+{duration(hour * 3600)}</span>
          </div>
          <div className="time-controls">
            <button
              type="button"
              className="play-btn"
              aria-label={playing ? 'Pause' : 'Play the trip'}
              onClick={() => {
                if (hour >= plan.slider_hours) setHour(0)
                setPlaying(!playing)
              }}
            >
              {playing ? '❚❚' : '▶'}
            </button>
            <input
              className="slider"
              type="range"
              min={0}
              max={plan.slider_hours}
              step={SLIDER_STEP_H}
              value={hour}
              onChange={(e) => {
                setPlaying(false)
                setHour(Number(e.target.value))
              }}
              aria-label="Forecast time after departure"
            />
          </div>
          <div className="time-scale muted">
            <span>Departure</span>
            <span>+{Math.round(plan.slider_hours / 2)}h</span>
            <span>+{plan.slider_hours}h</span>
          </div>
          <p className="truck-status muted">🚚 {truckStatus}</p>
        </div>
      )}
    </div>
  )
}
