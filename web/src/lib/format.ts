export const pct = (p: number, digits = 1) => `${(p * 100).toFixed(digits)}%`

export const gridLabel = (grid: number) => (grid === 0 ? 'PIT' : `P${grid}`)

export function countdown(targetIso: string, now: number) {
  const ms = new Date(targetIso).getTime() - now
  if (ms <= 0) return null
  const d = Math.floor(ms / 86_400_000)
  const h = Math.floor((ms % 86_400_000) / 3_600_000)
  const m = Math.floor((ms % 3_600_000) / 60_000)
  const s = Math.floor((ms % 60_000) / 1000)
  return { d, h, m, s }
}

export const raceDate = (iso: string) =>
  new Date(iso).toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' })

export const raceTime = (iso: string) =>
  new Date(iso).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', timeZoneName: 'short' })

export const shortRaceName = (name: string) => name.replace('Grand Prix', 'GP')
