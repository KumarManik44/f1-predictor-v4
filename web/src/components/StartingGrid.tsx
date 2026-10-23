import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core'
import { SortableContext, arrayMove, rectSortingStrategy, sortableKeyboardCoordinates, useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import type { Driver, GridState } from '../lib/types'
import { teamColor, teamName } from '../lib/teams'
import { raceDate, raceTime } from '../lib/format'

export type LoadStatus = 'idle' | 'loading' | 'unpublished' | 'loaded' | 'error'

interface Props {
  grid: GridState
  drivers: Map<string, Driver>
  round: number
  qualiUtc: string
  qualiDone: boolean
  loadStatus: LoadStatus
  onReorder: (order: string[]) => void
  onTogglePit: (driverId: string) => void
  onReset: () => void
  onLoadOfficial: () => void
}

function Slot({ id, index, driver, pit, onTogglePit }: {
  id: string
  index: number
  driver: Driver
  pit: boolean
  onTogglePit: (driverId: string) => void
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id })
  const color = teamColor(driver.constructor_id)
  const team = teamName(driver.constructor_id, driver.constructor_name)

  return (
    <li className={index % 2 === 1 ? 'pt-9' : ''}>
      <div className="mb-2 flex items-baseline justify-between px-0.5 font-mono text-[11px]">
        <span className={pit ? 'text-faint line-through' : 'text-muted'}>P{index + 1}</span>
        {pit && <span className="font-semibold text-warn">PIT LANE</span>}
      </div>
      <div
        ref={setNodeRef}
        style={{ transform: CSS.Transform.toString(transform), transition }}
        className={`grid-box ${isDragging ? 'relative z-20' : ''}`}
      >
        <div
          {...attributes}
          {...listeners}
          aria-label={`P${index + 1}: ${driver.given_name} ${driver.family_name}, ${team}${pit ? ', pit-lane start' : ''}. Press space to pick up, arrow keys to move.`}
          className={`relative flex cursor-grab touch-none select-none items-center gap-2 overflow-hidden rounded-xl border py-2.5 pl-3.5 pr-1.5 transition-[border-color,box-shadow,opacity] ${
            isDragging
              ? 'cursor-grabbing border-line-strong bg-panel shadow-[0_18px_40px_-14px_rgba(18,19,22,0.45)]'
              : 'border-line bg-panel hover:border-line-strong hover:shadow-sm'
          } ${pit ? 'border-dashed opacity-55' : ''}`}
        >
          <span className="absolute inset-y-0 left-0 w-1" style={{ background: color }} />
          <span className="font-display text-lg font-black italic leading-none tracking-tight">{driver.code}</span>
          <span className="min-w-0 flex-1 leading-tight">
            <span className="block truncate text-xs text-ink/80">{driver.family_name}</span>
            <span className="block truncate text-[10px] text-faint">{team}</span>
          </span>
          <button
            type="button"
            onPointerDown={(e) => e.stopPropagation()}
            onKeyDown={(e) => e.stopPropagation()}
            onClick={() => onTogglePit(id)}
            aria-pressed={pit}
            aria-label={`${pit ? 'Undo pit-lane start for' : 'Pit-lane start for'} ${driver.family_name}`}
            className={`shrink-0 rounded-md px-1.5 py-1 font-mono text-[10px] font-semibold transition ${
              pit ? 'bg-warn/20 text-warn' : 'text-faint hover:bg-black/5 hover:text-ink'
            }`}
          >
            PIT
          </button>
        </div>
      </div>
    </li>
  )
}

function LoadButton({ status, qualiDone, onClick }: { status: LoadStatus; qualiDone: boolean; onClick: () => void }) {
  const label = {
    idle: 'Load official qualifying',
    loading: 'Loading…',
    unpublished: 'Not published yet · retry',
    loaded: 'Official grid loaded',
    error: 'Couldn’t reach Jolpica · retry',
  }[status]
  const highlight = qualiDone && status !== 'loaded'

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={status === 'loading'}
      className={`rounded-full px-3.5 py-1.5 text-xs font-semibold transition disabled:opacity-60 ${
        highlight
          ? 'bg-accent text-white shadow-[0_8px_20px_-8px_rgba(227,38,27,0.7)] hover:brightness-110'
          : status === 'loaded'
            ? 'border border-good/40 text-good'
            : 'border border-line-strong text-ink hover:border-accent'
      }`}
    >
      {status === 'loaded' ? '✓ ' : ''}
      {label}
    </button>
  )
}

export default function StartingGrid(props: Props) {
  const { grid, drivers, round, qualiUtc, qualiDone, loadStatus, onReorder, onTogglePit, onReset, onLoadOfficial } = props
  const pit = new Set(grid.pitLane)
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  const onDragEnd = ({ active, over }: DragEndEvent) => {
    if (!over || active.id === over.id) return
    onReorder(arrayMove(grid.order, grid.order.indexOf(String(active.id)), grid.order.indexOf(String(over.id))))
  }

  return (
    <div className="panel p-4 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-display text-2xl font-black uppercase italic tracking-tight">Starting grid</h2>
          <p className="mt-1 text-xs text-muted">
            <span className={`mr-1.5 inline-block h-1.5 w-1.5 rounded-full align-middle ${grid.official ? 'bg-good' : 'bg-warn'}`} />
            {grid.source}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <LoadButton status={loadStatus} qualiDone={qualiDone} onClick={onLoadOfficial} />
          <button
            type="button"
            onClick={onReset}
            className="rounded-full border border-line px-3.5 py-1.5 text-xs font-semibold text-muted transition hover:border-line-strong hover:text-ink"
          >
            Reset
          </button>
        </div>
      </div>

      <p className="mt-4 rounded-lg bg-black/[0.035] px-3 py-2 text-[11px] leading-relaxed text-muted">
        {loadStatus === 'unpublished'
          ? `R${round} qualifying isn’t published yet (session: ${raceDate(qualiUtc)} ${raceTime(qualiUtc)}). Set the grid yourself meanwhile.`
          : 'Drag drivers to set the grid, tap PIT for a pit-lane start. Keyboard: focus a driver, Space to pick up, arrows to move.'}
      </p>

      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
        <SortableContext items={grid.order} strategy={rectSortingStrategy}>
          <ol className="mt-6 grid grid-cols-2 gap-x-3 gap-y-3 sm:gap-x-5">
            {grid.order.map((id, index) => (
              <Slot key={id} id={id} index={index} driver={drivers.get(id)!} pit={pit.has(id)} onTogglePit={onTogglePit} />
            ))}
          </ol>
        </SortableContext>
      </DndContext>
    </div>
  )
}
