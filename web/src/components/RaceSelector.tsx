import { motion } from 'motion/react'
import type { Race } from '../lib/types'
import { raceDate, shortRaceName } from '../lib/format'

interface Props {
  races: Race[]
  selected: number
  onSelect: (round: number) => void
}

export default function RaceSelector({ races, selected, onSelect }: Props) {
  return (
    <nav aria-label="Remaining races" className="no-scrollbar -mx-4 mt-6 overflow-x-auto px-4 sm:-mx-6 sm:px-6">
      <ul className="flex min-w-max gap-3 pb-2">
        {races.map((race, i) => {
          const active = race.round === selected
          return (
            <li key={race.round}>
              <button
                type="button"
                onClick={() => onSelect(race.round)}
                aria-pressed={active}
                className={`relative w-44 overflow-hidden rounded-2xl border p-4 text-left transition duration-300 ${
                  active
                    ? 'border-accent/50 bg-panel shadow-[0_14px_36px_-18px_rgba(227,38,27,0.55)]'
                    : 'border-line bg-panel/70 hover:border-line-strong hover:bg-panel'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`font-mono text-xs ${active ? 'text-accent' : 'text-faint'}`}>R{race.round}</span>
                  {i === 0 && (
                    <span className="rounded-full bg-accent/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-accent">
                      Next
                    </span>
                  )}
                </div>
                <div className="mt-3 font-display text-lg font-bold leading-tight">{shortRaceName(race.name)}</div>
                <div className="truncate text-xs text-muted">
                  {race.locality}, {race.country}
                </div>
                <div className="mt-3 font-mono text-xs text-faint">{raceDate(race.race_utc)}</div>
                {active && <motion.span layoutId="race-active" className="absolute inset-x-0 bottom-0 h-[3px] bg-accent" />}
              </button>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
