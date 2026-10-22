import type { CSSProperties } from 'react'
import { LEVELS, riskColor } from './format'

// Display copy of the thresholds the backend applies (backend/planner/risk.py).
const THRESHOLDS = [
  ['< 25', '< 0.10', '< 0.5'],
  ['25–34', '0.10–0.25', '0.5–1.0'],
  ['35–44', '0.25–0.50', '1.0–2.0'],
  ['45–54', '0.50–1.00', '2.0–3.0'],
  ['≥ 55', '> 1.00', '> 3.0'],
]

/** Map legend; opens to show what each risk level means. */
export function RiskLegend() {
  return (
    <details className="legend card">
      <summary>
        <span className="eyebrow">Risk</span>
        {LEVELS.map((name, i) => (
          <span key={name} className="chip" style={{ '--risk': riskColor(i) } as CSSProperties}>{name}</span>
        ))}
      </summary>
      <table className="num">
        <thead>
          <tr><th /><th>Wind mph</th><th>Rain in/hr</th><th>Snow in/hr</th></tr>
        </thead>
        <tbody>
          {THRESHOLDS.map((row, i) => (
            <tr key={i}>
              <th className="chip" style={{ '--risk': riskColor(i) } as CSSProperties}>{LEVELS[i]}</th>
              {row.map((cell) => <td key={cell}>{cell}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted">
        Heavier loads raise wind risk: 35–44 mph over 40,000 lb is Severe; 45–54 mph over 30,000 lb is No Travel.
        A checkpoint takes its worst condition.
      </p>
    </details>
  )
}
