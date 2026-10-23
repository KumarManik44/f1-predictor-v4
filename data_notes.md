# Data Notes (Phase 1)

Snapshot: `entries_2026_R17_68ee1ec64f65.parquet` (hash `68ee1ec64f65`)
Rows: 2,212 | Races: 109 | Podium rate: 14.8%

## Source
- Jolpica (Ergast-compatible) races, results, qualifying. Raw JSON cached per race in `data/raw/`.
- Stable IDs: `driver_id`, `constructor_id`, `circuit_id` (never names or 3-letter codes).
- FastF1 is not used (403 errors in an earlier environment).

## Rules
- **Row and target:** one row per driver per race (from race results). `y_podium = 1` only if
  the official classification is P1, P2 or P3. DNF, DNS and disqualified drivers have `y_podium = 0`.
- **Disqualified:** status text contains "disqualified" or positionText is "D". Count: 10.
- **Did not start:** status text contains "did not start" or positionText is "W". Count: 19.
- **Pit-lane starts:** grid 0 for a driver who did start, flagged `pit_lane_start`. Count: 13.
- **Missing qualifying row:** kept with NaN Q times and `has_quali_row = False`. Count: 6.
- **Races with no Q1 times:** ['2025 R6']. Q times stay NaN, never 0.
- **Cutoff:** `quali_datetime_utc` = the qualifying session that sets the Grand Prix grid.

## Known gaps
- Session date flags (qualifying not 0-3 days before race): none.
- Jolpica dates were reported wrong for Las Vegas 2023 and 2024 (see Phase 1 date check output).
- 2022 sprint weekends: the sprint (not qualifying) set the Grand Prix grid. Version 1 ignores
  sprints, so the cutoff for those races is treated as qualifying.
- Drivers who qualified but have no race result row (withdrawn before the race) are not rows.

## Date fixes (Phase 1, STEP 5)
- Las Vegas 2023 R21: qualifying 2023-11-17 08:00 UTC -> 2023-11-18 08:00 UTC (race time was correct).
- Las Vegas 2024 R22: qualifying 2024-11-22 06:00 -> 2024-11-23 06:00 UTC, race 2024-11-23 06:00 -> 2024-11-24 06:00 UTC.
- Las Vegas 2025 matched the official timetable, no fix.
- The race order does not change (next races are a week later), so only the cutoff timestamps move.
