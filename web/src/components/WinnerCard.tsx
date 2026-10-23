import { AnimatePresence, motion } from 'motion/react'
import type { Prediction } from '../lib/types'
import { teamColor, teamName } from '../lib/teams'
import { gridLabel, pct } from '../lib/format'
import AnimatedPercent from './AnimatedPercent'

const OTHERS_BELOW = 0.03   // drivers under 3% win chance are pooled into one segment

function WinSplit({ predictions }: { predictions: Prediction[] }) {
  const sorted = [...predictions].sort((a, b) => b.pWin - a.pWin)
  const named = sorted.filter((p) => p.pWin >= OTHERS_BELOW)
  const others = sorted.filter((p) => p.pWin < OTHERS_BELOW).reduce((sum, p) => sum + p.pWin, 0)

  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between text-[11px] uppercase tracking-[0.2em] text-faint">
        <span>Who wins? Share of 100%</span>
      </div>
      <div className="flex h-3 w-full gap-[2px] overflow-hidden rounded-full" role="img" aria-label="Win probability split">
        {named.map((p) => (
          <motion.div
            key={p.driver.driver_id}
            layout
            className="h-full first:rounded-l-full"
            animate={{ flexGrow: p.pWin }}
            style={{ flexBasis: 0, background: teamColor(p.driver.constructor_id) }}
            title={`${p.driver.code} ${pct(p.pWin)}`}
          />
        ))}
        {others > 0 && (
          <motion.div layout className="h-full rounded-r-full bg-black/15" animate={{ flexGrow: others }} style={{ flexBasis: 0 }} title={`Rest of field ${pct(others)}`} />
        )}
      </div>
      <div className="mt-2.5 flex flex-wrap gap-x-4 gap-y-1 text-xs">
        {named.map((p) => (
          <span key={p.driver.driver_id} className="flex items-center gap-1.5 text-muted">
            <span className="h-2 w-2 rounded-sm" style={{ background: teamColor(p.driver.constructor_id) }} />
            <span className="font-semibold text-ink">{p.driver.code}</span> {pct(p.pWin)}
          </span>
        ))}
        {others > 0 && (
          <span className="flex items-center gap-1.5 text-muted">
            <span className="h-2 w-2 rounded-sm bg-black/15" />
            Rest of field {pct(others)}
          </span>
        )}
      </div>
    </div>
  )
}

export default function WinnerCard({ predictions }: { predictions: Prediction[] }) {
  const winner = predictions.reduce((best, p) => (p.pWin > best.pWin ? p : best))
  const color = teamColor(winner.driver.constructor_id)

  return (
    <section aria-label="Predicted winner" className="panel relative overflow-hidden p-6 sm:p-8">
      <motion.div
        className="pointer-events-none absolute -right-28 -top-28 h-96 w-96 rounded-full opacity-[0.16] blur-3xl"
        animate={{ background: color }}
        transition={{ duration: 0.6 }}
      />
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.045]"
        style={{ backgroundImage: 'repeating-linear-gradient(115deg, #121316 0 1px, transparent 1px 16px)' }}
      />

      <div className="relative flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-muted">Predicted winner</p>
          <AnimatePresence mode="popLayout" initial={false}>
            <motion.div
              key={winner.driver.driver_id}
              initial={{ opacity: 0, x: -28 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 28 }}
              transition={{ type: 'spring', stiffness: 260, damping: 26 }}
            >
              <div className="mt-2 font-display text-7xl font-black italic leading-[0.85] tracking-tighter sm:text-8xl" style={{ color }}>
                {winner.driver.code}
              </div>
              <div className="mt-3 text-xl font-semibold">
                {winner.driver.given_name} {winner.driver.family_name}
              </div>
              <div className="text-sm text-muted">
                {teamName(winner.driver.constructor_id, winner.driver.constructor_name)} · starts {gridLabel(winner.grid)}
              </div>
            </motion.div>
          </AnimatePresence>
        </div>

        <div className="flex gap-8 sm:block sm:text-right">
          <div>
            <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-muted">Win chance</p>
            <AnimatedPercent value={winner.pWin} className="block font-mono text-5xl font-semibold tabular-nums sm:text-6xl" />
          </div>
          <div className="sm:mt-3">
            <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-muted">Podium chance</p>
            <AnimatedPercent value={winner.pPodium} className="block font-mono text-2xl tabular-nums text-ink/80" />
          </div>
        </div>
      </div>

      <div className="relative mt-8">
        <WinSplit predictions={predictions} />
      </div>
    </section>
  )
}
