import { useState } from 'react'
import { MapView } from './MapView'
import { RouteList } from './RouteList'
import { TripForm } from './TripForm'
import type { Plan, TripInput } from './types'

export default function App() {
  const [plan, setPlan] = useState<Plan | null>(null)
  const [selected, setSelected] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function findRoutes(input: TripInput) {
    setLoading(true)
    setError('')
    try {
      const res = await fetch('/api/plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(input),
      })
      const data = await res.json().catch(() => ({ error: `The server sent an unexpected response (HTTP ${res.status}).` }))
      if (!res.ok) throw new Error(data.error ?? 'Something went wrong.')
      setPlan(data)
      setSelected(0)
    } catch (e) {
      setError(e instanceof TypeError ? 'Could not reach the server. Check your connection.' : (e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <header className="brand">
          <span className="brand-mark" aria-hidden="true" />
          <div>
            <h1>RouteRisk</h1>
            <p className="muted">Weather-aware truck routing</p>
          </div>
        </header>

        <TripForm loading={loading} onSubmit={findRoutes} />

        {error && <div className="banner danger" role="alert">{error}</div>}
        {loading ? (
          <div className="results" aria-busy="true">
            {[0, 1, 2].map((i) => <div key={i} className="skeleton route-skeleton" />)}
          </div>
        ) : plan ? (
          <RouteList plan={plan} selected={selected} onSelect={setSelected} />
        ) : (
          <p className="muted hint">
            Enter a trip to compare three routes. Weather is checked at each checkpoint for the hour the truck
            gets there, then scored with the wind, rain, snow and load rules. Arrival times include the
            legally required driver breaks (30 min after 8 h driving, 10 h off after 11 h).
          </p>
        )}
      </aside>
      <MapView plan={plan} selected={selected} onSelect={setSelected} />
    </div>
  )
}
