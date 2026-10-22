import type { FeatureCollection, Point } from 'geojson'

export type Level = 0 | 1 | 2 | 3 | 4

export interface TripInput {
  origin: string
  destination: string
  departure: string
  load_lb: number
  interval_mi: number
}

export interface Checkpoint {
  mile: number
  lng: number
  lat: number
  eta: string
  wind: number
  rain: number
  snow: number
  level: Level
  factors: { wind: Level; rain: Level; snow: Level }
  reason: string
}

export interface Hazard {
  level: Level
  from_mi: number
  to_mi: number
  reason: string
  eta: string
  lng: number
  lat: number
}

/** A required hours-of-service stop: 30 min break or 10 h off duty. */
export interface Stop {
  kind: 'break' | 'rest'
  mile: number
  lng: number
  lat: number
  start: string
  end: string
}

export interface Place {
  label: string
  lng: number
  lat: number
}

export interface Route {
  via: string
  distance_mi: number
  drive_s: number
  stops: Stop[]
  summary: { no_travel_mi: number; severe_mi: number; high_mi: number; avg_risk: number; duration_s: number }
  hazards: Hazard[]
  track: [number, number, number][] // [lng, lat, seconds after departure]
  checkpoints: Checkpoint[]
  segments: { level: Level; coords: [number, number][] }[]
}

export interface Plan {
  origin: Place
  destination: Place
  departure: string
  forecast_start: string
  slider_hours: number
  heatmap_cell_deg: number
  routes: Route[]
  reason: string
  all_no_travel: boolean
  notes: string[]
  heatmap: FeatureCollection<Point>
}
