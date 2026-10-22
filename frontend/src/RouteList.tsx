import type { CSSProperties } from 'react'
import { dateTime, driveSummary, duration, LEVELS, riskColor } from './format'
import type { Hazard, Plan } from './types'

const MAX_HAZARDS = 4
const riskStyle = (level: number) => ({ '--risk': riskColor(level) }) as CSSProperties

function Hazards({ hazards }: { hazards: Hazard[] }) {
  if (!hazards.length) {
    return <p className="chip hazard-none" style={riskStyle(0)}>Low risk the whole way</p>
  }
  const worstFirst = [...hazards].sort((a, b) => b.level - a.level || a.from_mi - b.from_mi)
  return (
    <ul className="hazards" aria-label="Hazards on this route">
      {worstFirst.slice(0, MAX_HAZARDS).map((h) => (
        <li key={h.from_mi} style={riskStyle(h.level)}>
          <span className="chip">{LEVELS[h.level]}</span>
          <span className="hazard-reason">{h.reason}</span>
          <span className="muted num">
            mi {h.from_mi}–{h.to_mi} · {dateTime(h.eta)}
          </span>
        </li>
      ))}
      {hazards.length > MAX_HAZARDS && <li className="muted">+{hazards.length - MAX_HAZARDS} more stretches</li>}
    </ul>
  )
}

export function RouteList({ plan, selected, onSelect }: { plan: Plan; selected: number; onSelect: (i: number) => void }) {
  return (
    <section className="results" aria-label="Route options">
      {plan.all_no_travel && (
        <div className="banner danger" role="alert">
          Every route crosses No Travel conditions. Consider delaying departure.
        </div>
      )}
      {plan.notes.map((note) => (
        <div className="banner" key={note}>{note}</div>
      ))}

      <ul className="route-list">
        {plan.routes.map((route, i) => {
          const { summary } = route
          const worst = Math.max(...route.checkpoints.map((c) => c.level))
          const isSelected = i === selected
          return (
            <li key={i} className={`route-row${isSelected ? ' selected' : ''}`}>
              <button type="button" className="route-main" aria-pressed={isSelected} onClick={() => onSelect(i)}>
                <span className="route-text">
                  <span className="route-via">{route.via ? `via ${route.via}` : 'Local roads'}</span>
                  <span className="muted num">
                    {route.distance_mi.toLocaleString()} mi · arrives {dateTime(route.checkpoints.at(-1)!.eta)}
                  </span>
                  <span className="muted num">{driveSummary(route.drive_s, route.stops)}</span>
                  <span className="route-tags">
                    {i === 0 && <span className="badge">Recommended</span>}
                    <span className="chip" style={riskStyle(worst)}>Worst: {LEVELS[worst]}</span>
                  </span>
                </span>
                {/* Colored by worst risk, the way Google Maps colors travel time by traffic. */}
                <span className="route-time num" style={{ color: riskColor(worst) }}>
                  {duration(summary.duration_s)}
                </span>
              </button>
              {isSelected && (
                <div className="route-detail">
                  {i === 0 && <p className="why">{plan.reason}</p>}
                  <dl className="stats">
                    {([['No Travel mi', summary.no_travel_mi, 4], ['Severe mi', summary.severe_mi, 3], ['High mi', summary.high_mi, 2]] as const).map(
                      ([label, value, level]) => (
                        <div key={label}>
                          <dt>{label}</dt>
                          <dd style={value > 0 ? { color: riskColor(level) } : undefined}>{value}</dd>
                        </div>
                      ),
                    )}
                    <div>
                      <dt>Avg risk</dt>
                      <dd>{summary.avg_risk.toFixed(2)}</dd>
                    </div>
                  </dl>
                  <Hazards hazards={route.hazards} />
                </div>
              )}
            </li>
          )
        })}
      </ul>
    </section>
  )
}
