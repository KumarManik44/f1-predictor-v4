import type { ModelParams } from '../lib/types'
import { pct } from '../lib/format'

const SLOTS = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11+', 'pit']
const LABELS: Record<string, string> = { '11+': '11+', pit: 'PIT' }
const PODIUM_COLOR = '#2a2b30'
const WIN_COLOR = '#e3261b'

// Smoothed historical podium / win rate per starting slot (the lookup the model is built on)
export default function SlotChart({ podium, winner }: { podium: ModelParams; winner: ModelParams }) {
  const W = 640
  const H = 260
  const pad = { top: 16, right: 8, bottom: 28, left: 36 }
  const plotW = W - pad.left - pad.right
  const plotH = H - pad.top - pad.bottom
  const band = plotW / SLOTS.length
  const barW = Math.min(14, band / 3)
  const y = (v: number) => pad.top + plotH * (1 - v)
  const ticks = [0, 0.25, 0.5, 0.75, 1]

  // Bar with a 4px rounded top, anchored to the baseline
  const bar = (x: number, v: number) => {
    const top = y(v)
    const h = pad.top + plotH - top
    const r = Math.min(4, h, barW / 2)
    return `M${x},${pad.top + plotH} V${top + r} Q${x},${top} ${x + r},${top} H${x + barW - r} Q${x + barW},${top} ${x + barW},${top + r} V${pad.top + plotH} Z`
  }

  return (
    <figure>
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <figcaption>
          <h3 className="font-display text-xl font-bold uppercase italic">What a starting slot is worth</h3>
          <p className="text-xs text-muted">Smoothed historical rates by grid slot, 2022–2026. This lookup is the model’s backbone.</p>
        </figcaption>
        <div className="flex gap-4 text-xs text-muted">
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-3 rounded-sm" style={{ background: PODIUM_COLOR }} /> Podium
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-3 rounded-sm" style={{ background: WIN_COLOR }} /> Win
          </span>
        </div>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} className="mt-4 w-full" role="img" aria-label="Podium and win rate by starting slot">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={pad.left} x2={W - pad.right} y1={y(t)} y2={y(t)} stroke="rgba(18,19,22,0.08)" />
            <text x={pad.left - 8} y={y(t) + 3} textAnchor="end" className="fill-[#8b8c90] font-mono text-[10px]">
              {t * 100}%
            </text>
          </g>
        ))}
        {SLOTS.map((slot, i) => {
          const x0 = pad.left + i * band + band / 2 - barW - 1
          return (
            <g key={slot}>
              <title>{`${LABELS[slot] ?? `P${slot}`}: podium ${pct(podium.slot_rates[slot])}, win ${pct(winner.slot_rates[slot])}`}</title>
              <rect x={pad.left + i * band} y={pad.top} width={band} height={plotH} fill="transparent" />
              <path d={bar(x0, podium.slot_rates[slot])} fill={PODIUM_COLOR} />
              <path d={bar(x0 + barW + 2, winner.slot_rates[slot])} fill={WIN_COLOR} />
              <text x={pad.left + i * band + band / 2} y={H - 8} textAnchor="middle" className="fill-[#55565b] font-mono text-[10px]">
                {LABELS[slot] ?? `P${slot}`}
              </text>
            </g>
          )
        })}
        <text x={pad.left + band / 2 - barW / 2} y={y(podium.slot_rates['1']) - 6} textAnchor="middle" className="fill-[#121316] font-mono text-[10px]">
          {pct(podium.slot_rates['1'], 0)}
        </text>
        <text x={pad.left + band / 2 + barW / 2 + 1} y={y(winner.slot_rates['1']) - 6} textAnchor="middle" className="fill-[#121316] font-mono text-[10px]">
          {pct(winner.slot_rates['1'], 0)}
        </text>
      </svg>

      <table className="sr-only">
        <caption>Podium and win rate by starting slot</caption>
        <thead>
          <tr><th>Slot</th><th>Podium</th><th>Win</th></tr>
        </thead>
        <tbody>
          {SLOTS.map((slot) => (
            <tr key={slot}>
              <td>{LABELS[slot] ?? `P${slot}`}</td>
              <td>{pct(podium.slot_rates[slot])}</td>
              <td>{pct(winner.slot_rates[slot])}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  )
}
