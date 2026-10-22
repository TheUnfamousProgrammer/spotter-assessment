export const LEVELS = ['Low', 'Moderate', 'High', 'Severe', 'No Travel']

export const riskColor = (level: number) => `var(--risk-${level})`

export function duration(seconds: number) {
  const minutes = Math.round(seconds / 60)
  return `${Math.floor(minutes / 60)}h ${String(minutes % 60).padStart(2, '0')}m`
}

export function dateTime(value: string | Date) {
  return new Date(value).toLocaleString([], { weekday: 'short', hour: 'numeric', minute: '2-digit' })
}

export const STOP_LABELS = { break: '30 min break', rest: '10 h rest' }

/** "Drive 17h 48m + 1 × 10 h rest, 2 × 30 min break" */
export function driveSummary(driveS: number, stops: { kind: 'break' | 'rest' }[]) {
  const counts = (['rest', 'break'] as const)
    .map((kind) => [kind, stops.filter((s) => s.kind === kind).length] as const)
    .filter(([, n]) => n > 0)
    .map(([kind, n]) => `${n} × ${STOP_LABELS[kind]}`)
  return [`Drive ${duration(driveS)}`, counts.join(', ')].filter(Boolean).join(' + ')
}
