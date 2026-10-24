import { useEffect, useMemo, useState } from 'react'
import { MotionConfig } from 'motion/react'
import type { Driver, GridState, ModelFile, SeasonFile } from './lib/types'
import { predictGrid } from './lib/model'
import { fetchQualifying } from './lib/jolpica'
import Header from './components/Header'
import RaceSelector from './components/RaceSelector'
import RaceHero from './components/RaceHero'
import StartingGrid, { type LoadStatus } from './components/StartingGrid'
import WinnerCard from './components/WinnerCard'
import Podium from './components/Podium'
import FieldTable from './components/FieldTable'
import ModelCardSection from './components/ModelCardSection'
import Footer from './components/Footer'

function useNow(intervalMs = 1000) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), intervalMs)
    return () => clearInterval(timer)
  }, [intervalMs])
  return now
}

const editedSource = (source: string) => (source.endsWith('· edited') ? source : `${source} · edited`)

function Predictor({ model, season }: { model: ModelFile; season: SeasonFile }) {
  const now = useNow()
  const remaining = season.calendar.filter((race) => !race.completed)
  const [round, setRound] = useState(remaining[0].round)
  const [grids, setGrids] = useState<Record<number, GridState>>({})
  const [loadStatus, setLoadStatus] = useState<Record<number, LoadStatus>>({})
  const [extraDrivers, setExtraDrivers] = useState<Driver[]>([])

  const drivers = useMemo(
    () => new Map([...season.drivers, ...extraDrivers].map((d) => [d.driver_id, d])),
    [season.drivers, extraDrivers],
  )

  const race = remaining.find((r) => r.round === round)!
  const grid: GridState = grids[round] ?? {
    order: season.default_grid.order,
    pitLane: [],
    source: `Latest qualifying order (${season.latest_completed.name.replace('Grand Prix', 'GP')})`,
    official: false,
  }
  const setGrid = (next: GridState) => setGrids((prev) => ({ ...prev, [round]: next }))

  const predictions = useMemo(
    () => predictGrid(model.podium, model.winner, grid, drivers),
    [model, grid, drivers],
  )

  const onReorder = (order: string[]) => setGrid({ ...grid, order, source: editedSource(grid.source), official: false })

  const onTogglePit = (driverId: string) => {
    const pitLane = grid.pitLane.includes(driverId) ? grid.pitLane.filter((id) => id !== driverId) : [...grid.pitLane, driverId]
    setGrid({ ...grid, pitLane, source: editedSource(grid.source), official: false })
  }

  const onReset = () => {
    setGrids(({ [round]: _, ...rest }) => rest)
    setLoadStatus(({ [round]: _, ...rest }) => rest)
  }

  const onLoadOfficial = async () => {
    setLoadStatus((prev) => ({ ...prev, [round]: 'loading' }))
    try {
      const official = await fetchQualifying(season.season, round)
      if (!official) {
        setLoadStatus((prev) => ({ ...prev, [round]: 'unpublished' }))
        return
      }
      setExtraDrivers((prev) => [...prev, ...official.drivers.filter((d) => !drivers.has(d.driver_id))])
      setGrid({ order: official.order, pitLane: [], source: `Official R${round} qualifying`, official: true })
      setLoadStatus((prev) => ({ ...prev, [round]: 'loaded' }))
    } catch {
      setLoadStatus((prev) => ({ ...prev, [round]: 'error' }))
    }
  }

  return (
    <MotionConfig reducedMotion="user">
      <div id="top" className="bg-track relative min-h-screen">
        <Header card={model.card} />

        <main className="relative mx-auto max-w-7xl px-4 pb-8 sm:px-6">
          <RaceSelector races={remaining} selected={round} onSelect={setRound} />
          <RaceHero race={race} season={season.season} now={now} />

          <div className="mt-8 grid gap-6 lg:grid-cols-12">
            <div className="lg:col-span-5">
              <StartingGrid
                grid={grid}
                drivers={drivers}
                round={round}
                qualiUtc={race.quali_utc}
                qualiDone={new Date(race.quali_utc).getTime() + 90 * 60_000 < now}
                loadStatus={loadStatus[round] ?? 'idle'}
                onReorder={onReorder}
                onTogglePit={onTogglePit}
                onReset={onReset}
                onLoadOfficial={onLoadOfficial}
              />
            </div>
            <div className="space-y-6 lg:col-span-7">
              <WinnerCard predictions={predictions} />
              <Podium predictions={predictions} />
              <FieldTable predictions={predictions} />
            </div>
          </div>

          <ModelCardSection card={model.card} podium={model.podium} winner={model.winner} />
        </main>

        <Footer card={model.card} />
      </div>
    </MotionConfig>
  )
}

export default function App() {
  const [model, setModel] = useState<ModelFile | null>(null)
  const [season, setSeason] = useState<SeasonFile | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([
      fetch('./data/model.json').then((r) => r.json()),
      fetch('./data/season.json').then((r) => r.json()),
    ])
      .then(([m, s]) => {
        setModel(m)
        setSeason(s)
      })
      .catch((e) => setError(String(e)))
  }, [])

  if (error) return <div className="p-10 text-muted">Couldn’t load model data: {error}</div>
  if (!model || !season) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="kerb h-1 w-24 animate-pulse rounded-full" />
      </div>
    )
  }
  if (!season.calendar.some((race) => !race.completed)) {
    return <div className="p-10 text-muted">The {season.season} season is complete. See you next year.</div>
  }
  return <Predictor model={model} season={season} />
}
