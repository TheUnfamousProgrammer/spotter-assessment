/**
 * One-click trips for demos, found by scanning the live forecast for risky weather.
 * Forecasts change daily: refresh these before recording. A trip whose departure has
 * passed (or is beyond the 5-day forecast limit) is hidden automatically.
 */
export interface DemoTrip {
  label: string
  note: string
  origin: string
  destination: string
  departure: string // ISO, UTC
  load_lb: number
  interval_mi: number
}

export const DEMO_TRIPS: DemoTrip[] = [
  {
    label: 'Denver → Billings',
    note: 'Severe wind at 45,000 lb, High at 25,000 lb',
    origin: 'Denver, CO',
    destination: 'Billings, MT',
    departure: '2026-10-23T12:00:00Z',
    load_lb: 45000,
    interval_mi: 10,
  },
  {
    label: 'Salt Lake City → Bozeman',
    note: 'High snow on one alternative',
    origin: 'Salt Lake City, UT',
    destination: 'Bozeman, MT',
    departure: '2026-10-23T07:30:00Z',
    load_lb: 45000,
    interval_mi: 10,
  },
]
