import type { Driver, GridState, ModelParams, Prediction } from './types'

// Mirrors models.grid_slot / models.predict_from_params in the notebook exactly
export function gridSlot(grid: number): string {
  if (grid === 0) return 'pit'
  return grid <= 10 ? String(grid) : '11+'
}

export function predictRace(params: ModelParams, grids: number[]): number[] {
  const clip = params.logit_clip
  const raw = grids.map((grid) => {
    let rate = params.slot_rates[gridSlot(grid)] ?? params.base_rate
    rate = Math.min(Math.max(rate, clip), 1 - clip)
    const z = (Math.log(rate / (1 - rate)) - params.scaler_mean) / params.scaler_scale
    return 1 / (1 + Math.exp(-(params.intercept + params.coef * z)))
  })
  const total = raw.reduce((sum, p) => sum + p, 0)
  return raw.map((p) => Math.min((p * params.race_total) / total, params.p_cap))
}

// Grid number per driver: slot index + 1, or 0 for a pit-lane start (the slot stays empty)
export function gridNumbers(state: GridState): number[] {
  const pit = new Set(state.pitLane)
  return state.order.map((id, i) => (pit.has(id) ? 0 : i + 1))
}

export function predictGrid(
  podium: ModelParams,
  winner: ModelParams,
  state: GridState,
  drivers: Map<string, Driver>,
): Prediction[] {
  const grids = gridNumbers(state)
  const pPodium = predictRace(podium, grids)
  const pWin = predictRace(winner, grids)
  return state.order.map((id, i) => ({
    driver: drivers.get(id)!,
    grid: grids[i],
    pWin: pWin[i],
    pPodium: pPodium[i],
  }))
}
