// Shapes of the JSON exported by the notebook (data.export_web_data, models.save_final_models)

export interface ModelParams {
  model: string
  slot_rates: Record<string, number>
  base_rate: number
  logit_clip: number
  scaler_mean: number
  scaler_scale: number
  coef: number
  intercept: number
  race_total: number
  p_cap: number
}

export interface ScoreSummary {
  races: number
  brier: number
  brier_ci: [number, number]
  log_loss: number
  diff_vs_baseline: number
  diff_ci: [number, number]
  prob_sum_mean: number
  baseline_brier?: number
}

export interface TargetCard {
  model: string
  baseline: string
  dev: ScoreSummary
  holdout: ScoreSummary | null
  holdout_passed?: boolean
  note: string
}

export interface ModelCard {
  project: string
  trained_at: string
  trained_through: string
  snapshot_hash: string
  training_races: number
  training_rows: number
  inputs: string
  podium: TargetCard
  winner: TargetCard
}

export interface ModelFile {
  podium: ModelParams
  winner: ModelParams
  card: ModelCard
}

export interface Race {
  round: number
  name: string
  circuit_id: string
  circuit_name: string
  locality: string
  country: string
  race_utc: string
  quali_utc: string
  completed: boolean
}

export interface Driver {
  driver_id: string
  code: string
  number: string | null
  given_name: string
  family_name: string
  nationality: string | null
  constructor_id: string
  constructor_name: string
}

export interface SeasonFile {
  season: number
  exported_at: string
  latest_completed: { round: number; name: string }
  calendar: Race[]
  drivers: Driver[]
  default_grid: { source: string; order: string[] }
}

export interface GridState {
  order: string[]          // driver_ids, index 0 = P1
  pitLane: string[]        // driver_ids starting from the pit lane (their slot stays empty)
  source: string           // where this grid came from
  official: boolean        // true when loaded from published qualifying
}

export interface Prediction {
  driver: Driver
  grid: number             // 0 = pit lane
  pWin: number
  pPodium: number
}
