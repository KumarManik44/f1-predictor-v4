import { motion } from 'motion/react'
import type { Prediction } from '../lib/types'
import { teamColor, teamName } from '../lib/teams'
import { gridLabel } from '../lib/format'
import AnimatedPercent from './AnimatedPercent'

const STEP_HEIGHT = { 1: 'h-28 sm:h-32', 2: 'h-20 sm:h-24', 3: 'h-14 sm:h-16' } as const

export default function Podium({ predictions }: { predictions: Prediction[] }) {
  const top3 = [...predictions].sort((a, b) => b.pPodium - a.pPodium).slice(0, 3)
  const layout = [
    { rank: 2 as const, p: top3[1] },
    { rank: 1 as const, p: top3[0] },
    { rank: 3 as const, p: top3[2] },
  ]

  return (
    <section aria-label="Most likely podium" className="panel p-6 sm:p-8">
      <div className="flex items-baseline justify-between gap-4">
        <h2 className="font-display text-2xl font-black uppercase italic tracking-tight">Most likely podium</h2>
        <span className="text-xs text-muted">Top 3 by podium chance</span>
      </div>

      <ol className="mt-8 grid grid-cols-3 items-end gap-2 sm:gap-4">
        {layout.map(({ rank, p }) => {
          const color = teamColor(p.driver.constructor_id)
          return (
            <li key={rank} className={rank === 1 ? 'order-2' : rank === 2 ? 'order-1' : 'order-3'}>
              <motion.div key={p.driver.driver_id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="text-center">
                <div className="font-display text-3xl font-black italic leading-none tracking-tight sm:text-4xl" style={{ color }}>
                  {p.driver.code}
                </div>
                <div className="mt-1 truncate text-xs text-muted">
                  {teamName(p.driver.constructor_id, p.driver.constructor_name)} · {gridLabel(p.grid)}
                </div>
                <AnimatedPercent value={p.pPodium} className="mt-2 block font-mono text-lg font-semibold tabular-nums sm:text-xl" />
              </motion.div>
              <div
                className={`relative mt-3 overflow-hidden rounded-t-xl border border-b-0 border-line bg-gradient-to-b from-black/[0.06] to-black/[0.01] ${STEP_HEIGHT[rank]}`}
              >
                <div className="absolute inset-x-0 top-0 h-[3px]" style={{ background: color }} />
                <span className="absolute inset-0 flex items-center justify-center font-display text-4xl font-black italic text-black/10 sm:text-5xl">
                  {rank}
                </span>
              </div>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
