import type { ModelCard } from '../lib/types'

export function Logo({ className = 'h-7 w-7' }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden="true">
      <rect width="32" height="32" rx="7" fill="#121316" />
      <path d="M7 22 L14 10 H25 L23 13 H16 L14.5 15.5 H21 L19.2 18.5 H12.7 L10.6 22 Z" fill="#ff3d2e" />
    </svg>
  )
}

export default function Header({ card }: { card: ModelCard }) {
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-base/75 backdrop-blur-xl">
      <div className="kerb h-[3px] w-full opacity-90" />
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
        <a href="#top" className="flex items-center gap-2.5">
          <Logo />
          <span className="font-display text-lg font-black uppercase italic tracking-tight">F1 Predictor</span>
          <span className="rounded-md bg-accent px-1.5 py-0.5 font-mono text-[11px] font-semibold text-white">V4</span>
        </a>
        <div className="flex items-center gap-4 text-xs text-muted">
          <span className="hidden md:inline">
            Trained through <span className="text-ink">{card.trained_through.replace('Grand Prix', 'GP')}</span>
          </span>
          <a
            href="#model"
            className="rounded-full border border-line-strong px-3.5 py-1.5 font-medium text-ink transition hover:border-accent hover:text-accent"
          >
            How good is it?
          </a>
        </div>
      </div>
    </header>
  )
}
