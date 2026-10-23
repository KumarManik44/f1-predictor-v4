import type { ModelCard } from '../lib/types'
import { Logo } from './Header'

export default function Footer({ card }: { card: ModelCard }) {
  return (
    <footer className="mt-24 border-t border-line">
      <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-10 text-xs text-faint sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <div className="flex items-center gap-2.5">
          <Logo className="h-5 w-5" />
          <span>
            F1 Predictor V4 · trained on {card.training_races} races through {card.trained_through} · snapshot{' '}
            <span className="font-mono">{card.snapshot_hash}</span>
          </span>
        </div>
        <span>Data: Jolpica (Ergast-compatible). Not affiliated with Formula 1, the FIA or any team.</span>
      </div>
    </footer>
  )
}
