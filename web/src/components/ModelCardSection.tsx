import type { ModelCard, ModelParams, ScoreSummary } from '../lib/types'
import SlotChart from './SlotChart'

const f4 = (v: number) => v.toFixed(4)
const signed = (v: number) => `${v > 0 ? '+' : v < 0 ? '−' : '±'}${Math.abs(v).toFixed(4)}`

function ScoreTile({ title, subtitle, score }: { title: string; subtitle: string; score: ScoreSummary }) {
  const baseline = score.baseline_brier ?? score.brier - score.diff_vs_baseline
  const clearWin = score.diff_ci[1] < 0

  return (
    <div className="panel flex flex-col p-6">
      <p className="font-mono text-[11px] uppercase tracking-[0.25em] text-muted">{title}</p>
      <p className="text-xs text-faint">{subtitle}</p>

      <div className="mt-5 flex items-end gap-3">
        <span className="font-mono text-4xl font-semibold tabular-nums">{f4(score.brier)}</span>
        <span className="pb-1 text-xs text-muted">Brier</span>
      </div>
      <p className="mt-1 text-xs text-muted">
        Grid-slot baseline <span className="font-mono text-ink/80">{f4(baseline)}</span>
      </p>

      <div className="mt-5 border-t border-line pt-4">
        <p className="font-mono text-sm tabular-nums">
          Δ {signed(score.diff_vs_baseline)}{' '}
          <span className="text-faint">
            [{signed(score.diff_ci[0])}, {signed(score.diff_ci[1])}]
          </span>
        </p>
        <p className={`mt-2 inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${clearWin ? 'bg-good/10 text-good' : 'bg-warn/10 text-warn'}`}>
          <span aria-hidden="true">{clearWin ? '✓' : '≈'}</span>
          {clearWin ? 'Better than the baseline' : 'Not a clear win: interval crosses zero'}
        </p>
      </div>
    </div>
  )
}

export default function ModelCardSection({ card, podium, winner }: { card: ModelCard; podium: ModelParams; winner: ModelParams }) {
  return (
    <section id="model" className="mt-24 scroll-mt-24">
      <div className="kerb h-1 w-16 rounded-full" />
      <h2 className="mt-5 font-display text-4xl font-black uppercase italic leading-none tracking-tight sm:text-6xl">How good is it, honestly?</h2>
      <p className="mt-4 max-w-3xl text-muted">
        Scored with the <span className="text-ink">Brier score</span>: the average squared gap between the predicted chance and what
        actually happened. Lower is better. Saying 15% for every driver scores about 0.13. Every number below comes from races the model
        had not seen when it made the prediction.
      </p>

      <div className="mt-10 grid gap-4 md:grid-cols-3">
        <ScoreTile title="Podium · development" subtitle={`${card.podium.dev.races} races, 2024 R1 – 2026 R7`} score={card.podium.dev} />
        {card.podium.holdout && (
          <ScoreTile title="Podium · holdout" subtitle={`${card.podium.holdout.races} unseen races, opened once`} score={card.podium.holdout} />
        )}
        <ScoreTile title="Winner · development" subtitle={`${card.winner.dev.races} races (no clean holdout)`} score={card.winner.dev} />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-5">
        <div className="panel p-6 lg:col-span-3">
          <SlotChart podium={podium} winner={winner} />
        </div>

        <div className="panel p-6 lg:col-span-2">
          <h3 className="font-display text-xl font-bold uppercase italic">What we learned</h3>
          <ul className="mt-4 space-y-3 text-sm leading-relaxed text-muted">
            <li>
              <span className="text-ink">The grid is the signal.</span> Qualifying gaps, driver form, team strength and circuit history
              were each tested on top of it. None improved the score.
            </li>
            <li>
              <span className="text-ink">Bigger models did worse.</span> CatBoost and XGBoost on all 13 features lost to the simple
              grid-slot lookup.
            </li>
            <li>
              <span className="text-ink">So the same grid gives the same odds everywhere.</span> The race you pick labels the prediction;
              it doesn’t change it. No hand-tuned circuit multipliers.
            </li>
            <li>
              <span className="text-ink">Leak-proof.</span> Every feature was rebuilt with all later races deleted and came out identical
              in 109 of 109 races.
            </li>
            <li>
              <span className="text-ink">Why not accuracy?</span> Only 15% of drivers finish on the podium, so predicting “no podium”
              for everyone is already 85% accurate. V3 reported 93.9%; V4 reports Brier instead.
            </li>
          </ul>
        </div>
      </div>
    </section>
  )
}
