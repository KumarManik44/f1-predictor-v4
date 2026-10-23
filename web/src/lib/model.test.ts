import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { gridSlot, predictRace } from './model'
import type { ModelFile } from './types'

// Python's predictions for one real race (models.save_final_models → parity_fixture.json)
const load = (name: string) => JSON.parse(readFileSync(new URL(`../../public/data/${name}`, import.meta.url), 'utf8'))
const model: ModelFile = load('model.json')
const fixture = load('parity_fixture.json')

describe('browser model matches the Python model', () => {
  it('grid slots match models.grid_slot', () => {
    expect([1, 2, 10, 11, 20, 0].map(gridSlot)).toEqual(['1', '2', '10', '11+', '11+', 'pit'])
  })

  for (const target of ['podium', 'winner'] as const) {
    it(`${target}: every driver within 1e-12 of Python (${fixture.race})`, () => {
      const browser = predictRace(model[target], fixture.grid)
      const worst = Math.max(...browser.map((p, i) => Math.abs(p - fixture[target][i])))
      expect(worst).toBeLessThan(1e-12)
    })
  }

  it('probabilities sum to 3 (podium) and 1 (winner)', () => {
    const grid = Array.from({ length: 22 }, (_, i) => i + 1)
    expect(predictRace(model.podium, grid).reduce((a, b) => a + b, 0)).toBeCloseTo(3, 10)
    expect(predictRace(model.winner, grid).reduce((a, b) => a + b, 0)).toBeCloseTo(1, 10)
  })
})
