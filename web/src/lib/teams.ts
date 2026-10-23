// Team colours (2026 liveries, deepened to stay readable on the light background).
// Identity is never colour-only: every chip also shows the driver code and team name.
const TEAM_COLORS: Record<string, string> = {
  mclaren: '#f07100',
  ferrari: '#d9102a',
  red_bull: '#2b56a8',
  mercedes: '#00a39a',
  aston_martin: '#1b7a5a',
  alpine: '#d63f97',
  williams: '#1d8fd8',
  rb: '#5470e0',
  haas: '#8a8f96',
  audi: '#2e2f34',
  cadillac: '#a5822c',
}

const SHORT_NAMES: Record<string, string> = {
  mclaren: 'McLaren',
  ferrari: 'Ferrari',
  red_bull: 'Red Bull',
  mercedes: 'Mercedes',
  aston_martin: 'Aston Martin',
  alpine: 'Alpine',
  williams: 'Williams',
  rb: 'Racing Bulls',
  haas: 'Haas',
  audi: 'Audi',
  cadillac: 'Cadillac',
}

export const teamColor = (constructorId: string) => TEAM_COLORS[constructorId] ?? '#8b8c90'
export const teamName = (constructorId: string, fallback: string) => SHORT_NAMES[constructorId] ?? fallback
