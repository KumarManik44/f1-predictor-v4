import { motion } from 'motion/react'
import type { Prediction } from '../lib/types'
import { teamColor, teamName } from '../lib/teams'
import { gridLabel, pct } from '../lib/format'

const WIN_COLOR = '#e3261b'
const PODIUM_COLOR = '#2a2b30'

function Bar({ value, color, label }: { value: number; color: string; label: string }) {
  return (
    <div className="flex items-center gap-2" aria-label={`${label} ${pct(value)}`}>
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-black/[0.07]">
        <motion.div
          className="h-full rounded-full"
          style={{ background: color }}
          initial={false}
          animate={{ width: `${Math.max(value * 100, value > 0 ? 0.6 : 0)}%` }}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
        />
      </div>
      <span className="w-12 text-right font-mono text-xs tabular-nums text-ink/90">{pct(value)}</span>
    </div>
  )
}

export default function FieldTable({ predictions }: { predictions: Prediction[] }) {
  const rows = [...predictions].sort((a, b) => b.pPodium - a.pPodium || a.grid - b.grid)

  return (
    <section aria-label="Full field" className="panel p-4 sm:p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="font-display text-2xl font-black uppercase italic tracking-tight">Full field</h2>
        <div className="flex gap-4 text-xs text-muted">
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-3 rounded-sm" style={{ background: WIN_COLOR }} /> Win
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-3 rounded-sm" style={{ background: PODIUM_COLOR }} /> Podium
          </span>
        </div>
      </div>

      <div className="mt-4 hidden grid-cols-[2rem_minmax(0,1.3fr)_3rem_minmax(0,1fr)_minmax(0,1fr)] gap-4 px-2 text-[10px] uppercase tracking-[0.2em] text-faint sm:grid">
        <span>#</span>
        <span>Driver</span>
        <span>Grid</span>
        <span>Win</span>
        <span>Podium</span>
      </div>

      <ol className="mt-2">
        {rows.map((p, i) => (
          <motion.li
            key={p.driver.driver_id}
            layout
            transition={{ type: 'spring', stiffness: 380, damping: 36 }}
            className="grid grid-cols-[2rem_minmax(0,1fr)_3rem] items-center gap-x-4 gap-y-2 rounded-lg px-2 py-2.5 odd:bg-black/[0.025] sm:grid-cols-[2rem_minmax(0,1.3fr)_3rem_minmax(0,1fr)_minmax(0,1fr)]"
          >
            <span className="font-mono text-xs text-faint">{i + 1}</span>
            <span className="flex min-w-0 items-center gap-2.5">
              <span className="h-5 w-1 shrink-0 rounded-full" style={{ background: teamColor(p.driver.constructor_id) }} />
              <span className="font-display text-base font-bold italic text-ink">{p.driver.code}</span>
              <span className="truncate text-xs text-muted">
                {p.driver.family_name} · {teamName(p.driver.constructor_id, p.driver.constructor_name)}
              </span>
            </span>
            <span className={`font-mono text-xs ${p.grid === 0 ? 'text-warn' : 'text-muted'}`}>{gridLabel(p.grid)}</span>
            <div className="col-span-3 grid grid-cols-2 gap-4 sm:col-span-1 sm:block">
              <Bar value={p.pWin} color={WIN_COLOR} label="Win" />
              <div className="sm:hidden">
                <Bar value={p.pPodium} color={PODIUM_COLOR} label="Podium" />
              </div>
            </div>
            <div className="hidden sm:block">
              <Bar value={p.pPodium} color={PODIUM_COLOR} label="Podium" />
            </div>
          </motion.li>
        ))}
      </ol>
    </section>
  )
}
