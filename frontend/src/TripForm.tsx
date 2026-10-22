import { useState, type FormEvent } from 'react'
import { DEMO_TRIPS, type DemoTrip } from './demoTrips'
import { PlaceInput } from './PlaceInput'
import type { TripInput } from './types'

const HOUR = 3_600_000
const MAX_LEAD_DAYS = 5 // matches the backend: the forecast must cover the trip and the 48 h slider

// <input type="datetime-local"> wants local time without a zone: "2026-10-20T14:00".
function toLocalInput(date: Date) {
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16)
}

export function TripForm({ loading, onSubmit }: { loading: boolean; onSubmit: (input: TripInput) => void }) {
  const [origin, setOrigin] = useState('Chicago, IL')
  const [destination, setDestination] = useState('Denver, CO')
  const [leaveNow, setLeaveNow] = useState(true)
  const [departure, setDeparture] = useState(() => toLocalInput(new Date(Math.ceil(Date.now() / HOUR) * HOUR)))
  const [load, setLoad] = useState('40000')
  const [intervalMi, setIntervalMi] = useState(25)

  function submit(e: FormEvent) {
    e.preventDefault()
    onSubmit({
      origin,
      destination,
      departure: (leaveNow ? new Date() : new Date(departure)).toISOString(),
      load_lb: Number(load),
      interval_mi: intervalMi,
    })
  }

  function runDemo(trip: DemoTrip) {
    setOrigin(trip.origin)
    setDestination(trip.destination)
    setLeaveNow(false)
    setDeparture(toLocalInput(new Date(trip.departure)))
    setLoad(String(trip.load_lb))
    setIntervalMi(trip.interval_mi)
    const { origin, destination, departure, load_lb, interval_mi } = trip
    onSubmit({ origin, destination, departure, load_lb, interval_mi })
  }

  const now = Date.now()
  const demos = DEMO_TRIPS.filter((t) => {
    const at = Date.parse(t.departure)
    return at > now && at < now + MAX_LEAD_DAYS * 24 * HOUR
  })

  function swap() {
    setOrigin(destination)
    setDestination(origin)
  }

  return (
    <form className="trip-form" onSubmit={submit}>
      <div className="stops">
        <div className="stop-icons" aria-hidden="true">
          <span className="stop-dot" />
          <span className="stop-line" />
          <span className="stop-pin" />
        </div>
        <div className="stop-fields">
          <PlaceInput label="Origin" placeholder="Choose starting point" value={origin} onChange={setOrigin} />
          <PlaceInput label="Destination" placeholder="Choose destination" value={destination} onChange={setDestination} />
        </div>
        <button type="button" className="icon-btn" onClick={swap} aria-label="Swap origin and destination" title="Swap">
          ⇅
        </button>
      </div>

      <div className="form-row">
        <select
          className="input"
          aria-label="Departure"
          value={leaveNow ? 'now' : 'at'}
          onChange={(e) => setLeaveNow(e.target.value === 'now')}
        >
          <option value="now">Leave now</option>
          <option value="at">Depart at</option>
        </select>
        <label className="input-suffix">
          <input
            className="input num"
            type="number"
            aria-label="Load in pounds"
            min={0}
            max={80000}
            step={500}
            value={load}
            onChange={(e) => setLoad(e.target.value)}
            required
          />
          <span>lb</span>
        </label>
      </div>
      {!leaveNow && (
        <input
          className="input"
          type="datetime-local"
          aria-label="Departure time"
          value={departure}
          min={toLocalInput(new Date())}
          max={toLocalInput(new Date(Date.now() + MAX_LEAD_DAYS * 24 * HOUR))}
          onChange={(e) => setDeparture(e.target.value)}
          required
        />
      )}

      <div className="field" role="radiogroup" aria-label="Checkpoint interval">
        <span>Weather checkpoint every</span>
        <div className="seg">
          {[10, 25, 50].map((mi) => (
            <label key={mi}>
              <input type="radio" name="interval" checked={intervalMi === mi} onChange={() => setIntervalMi(mi)} />
              {mi} mi
            </label>
          ))}
        </div>
      </div>
      <button className="btn" type="submit" disabled={loading}>
        {loading ? 'Checking routes and weather…' : 'Find safest route'}
      </button>
      {demos.length > 0 && (
        <div className="demo-trips">
          <span className="eyebrow">Demo trips</span>
          {demos.map((trip) => (
            <button
              key={trip.label}
              type="button"
              className="demo-chip"
              disabled={loading}
              title={trip.note}
              onClick={() => runDemo(trip)}
            >
              <strong>{trip.label}</strong>
              <span className="muted">{trip.note}</span>
            </button>
          ))}
        </div>
      )}
    </form>
  )
}
