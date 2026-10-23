import type { Driver } from './types'

const JOLPICA = 'https://api.jolpi.ca/ergast/f1'

interface JolpicaQualifyingRow {
  position: string
  number?: string
  Driver: { driverId: string; code?: string; permanentNumber?: string; givenName: string; familyName: string; nationality?: string }
  Constructor: { constructorId: string; name: string }
}

export interface OfficialQualifying {
  order: string[]
  drivers: Driver[]
}

// Published Grand Prix qualifying for one round, or null if it is not out yet
export async function fetchQualifying(season: number, round: number): Promise<OfficialQualifying | null> {
  const response = await fetch(`${JOLPICA}/${season}/${round}/qualifying.json?limit=100`)
  if (!response.ok) throw new Error(`Jolpica returned ${response.status}`)
  const races = (await response.json()).MRData.RaceTable.Races
  if (!races.length) return null

  const rows: JolpicaQualifyingRow[] = [...races[0].QualifyingResults]
    .sort((a: JolpicaQualifyingRow, b: JolpicaQualifyingRow) => Number(a.position) - Number(b.position))
  const drivers: Driver[] = rows.map((q) => ({
    driver_id: q.Driver.driverId,
    code: q.Driver.code ?? q.Driver.familyName.slice(0, 3).toUpperCase(),
    number: q.Driver.permanentNumber ?? q.number ?? null,
    given_name: q.Driver.givenName,
    family_name: q.Driver.familyName,
    nationality: q.Driver.nationality ?? null,
    constructor_id: q.Constructor.constructorId,
    constructor_name: q.Constructor.name,
  }))
  return { order: drivers.map((d) => d.driver_id), drivers }
}
