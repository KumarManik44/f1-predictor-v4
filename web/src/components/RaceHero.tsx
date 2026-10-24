import { AnimatePresence, motion } from 'motion/react'
import type { Race } from '../lib/types'
import { countdown } from '../lib/format'

function Unit({ value, label }: { value: number; label: string }) {
  return (
    <div className="flex flex-col items-center">
      <span className="min-w-[3.25rem] glass-chip rounded-xl border border-white/60 px-2 py-2 text-center font-mono text-2xl font-semibold tabular-nums sm:text-3xl">
        {String(value).padStart(2, '0')}
      </span>
      <span className="mt-1.5 text-[10px] uppercase tracking-[0.2em] text-faint">{label}</span>
    </div>
  )
}

export default function RaceHero({ race, season, now }: { race: Race; season: number; now: number }) {
  const left = countdown(race.race_utc, now)

  return (
    <section className="mt-8 flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
      <div className="min-w-0">
        <div className="font-mono text-xs uppercase tracking-[0.25em] text-muted">
          <span className="text-accent">Round {race.round}</span> · {season} season
        </div>
        <AnimatePresence mode="wait">
          <motion.h1
            key={race.round}
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -14 }}
            transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
            className="mt-3 font-display text-4xl font-black uppercase italic leading-[0.9] tracking-tight sm:text-6xl lg:text-7xl"
          >
            {race.name}
          </motion.h1>
        </AnimatePresence>
      </div>

      <div aria-live="off">
        <p className="mb-2 text-[11px] uppercase tracking-[0.25em] text-muted">{left ? 'Lights out in' : 'Race underway'}</p>
        {left && (
          <div className="flex gap-2">
            <Unit value={left.d} label="Days" />
            <Unit value={left.h} label="Hrs" />
            <Unit value={left.m} label="Min" />
            <Unit value={left.s} label="Sec" />
          </div>
        )}
      </div>
    </section>
  )
}
