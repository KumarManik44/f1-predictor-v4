# ========================================
# F1 PREDICTOR V4 - data.py
# Phase 1: Jolpica collection, caching, entries table, snapshot
# ========================================

import json
import time
import hashlib
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import requests

JOLPICA_BASE = 'https://api.jolpi.ca/ergast/f1'
REQUEST_PAUSE = 0.3   # seconds between live calls (Jolpica burst limit: 4 per second)


# ========================================
# STEP 1: Fetch + Cache Raw JSON
# ========================================

def fetch_json(url, cache_path, refresh=False, retries=5):
    """
    Return Jolpica JSON from the cache if present, otherwise call the API

    Parameters:
    - url: Jolpica endpoint
    - cache_path: file to read from / write to
    - refresh: ignore the cache and call the API again (default: False)
    - retries: attempts when rate limited (HTTP 429)

    Returns:
    - (payload dict, from_cache bool)

    Empty responses (race not run yet) are never cached.
    """
    cache_path = Path(cache_path)
    if cache_path.exists() and not refresh:
        return json.loads(cache_path.read_text()), True

    for attempt in range(retries):
        response = requests.get(url, timeout=30)

        if response.status_code == 429:
            wait = 5 * 2 ** attempt
            print(f"   ⏳ Rate limited, waiting {wait}s...")
            time.sleep(wait)
            continue

        response.raise_for_status()
        time.sleep(REQUEST_PAUSE)
        payload = response.json()

        if payload['MRData']['RaceTable']['Races']:
            cache_path.write_text(json.dumps(payload))
        return payload, False

    raise RuntimeError(f"Still rate limited after {retries} attempts: {url}")


def collect_raw_data(seasons, raw_dir, today=None):
    """
    Collect schedule, results and qualifying JSON for every completed race

    Parameters:
    - seasons: list of seasons (e.g., [2022, ..., 2026])
    - raw_dir: folder for cached raw JSON (one file per race per endpoint)
    - today: races on or after this date are skipped (default: today)

    Returns:
    - Dict with 'schedule' (list of race dicts), 'results' and 'qualifying'
      (dicts keyed by (season, round))
    """
    raw_dir = Path(raw_dir)
    today = pd.Timestamp(today or date.today())
    schedule, results, qualifying = [], {}, {}
    api_calls = 0

    print(f"📊 COLLECTING RAW DATA ({seasons[0]}-{seasons[-1]})")
    print("   Source: Jolpica (Ergast-compatible), cached per race in data/raw\n")

    for season in seasons:
        payload, cached = fetch_json(f"{JOLPICA_BASE}/{season}/races.json?limit=100",
                                     raw_dir / f"{season}_schedule.json")
        api_calls += not cached
        races = payload['MRData']['RaceTable']['Races']
        schedule.extend(races)

        completed = [race for race in races if pd.Timestamp(race['date']) < today]
        found = {'results': 0, 'qualifying': 0}

        for race in completed:
            race_round = int(race['round'])

            for kind, store in [('results', results), ('qualifying', qualifying)]:
                payload, cached = fetch_json(
                    f"{JOLPICA_BASE}/{season}/{race_round}/{kind}.json?limit=100",
                    raw_dir / f"{season}_{race_round:02d}_{kind}.json"
                )
                api_calls += not cached
                race_table = payload['MRData']['RaceTable']['Races']

                if race_table:
                    store[(season, race_round)] = race_table[0]
                    found[kind] += 1

        status = "✅" if found['results'] == len(completed) else "⚠️ "
        print(f"🏎️  Season {season}: {len(races)} on calendar | {len(completed)} completed | "
              f"results {found['results']} | qualifying {found['qualifying']} {status}")

    print(f"\n✅ Collected: {len(results)} races with results, {len(qualifying)} with qualifying")
    print(f"🌐 Live API calls this run: {api_calls} (everything else from cache)")

    return {'schedule': schedule, 'results': results, 'qualifying': qualifying}


# ========================================
# STEP 2: Parse + Merge Into Entries Table
# ========================================

def lap_time_to_seconds(lap_time):
    """Convert '1:29.708' to 89.708 seconds, missing or blank stays NaN"""
    if not isinstance(lap_time, str) or ':' not in lap_time:
        return np.nan
    minutes, seconds = lap_time.split(':')
    return int(minutes) * 60 + float(seconds)


def session_to_utc(session):
    """Combine a Jolpica session's date + time into a UTC timestamp (NaT if missing)"""
    if not session or 'date' not in session:
        return pd.NaT
    return pd.to_datetime(f"{session['date']}T{session.get('time', '00:00:00Z')}", utc=True)


def parse_schedule(schedule):
    """
    One row per race on the calendar

    Returns:
    - DataFrame: season, round, race_name, circuit_id, race_datetime_utc, quali_datetime_utc
    """
    races = pd.DataFrame([{
        'season': int(race['season']),
        'round': int(race['round']),
        'race_name': race['raceName'],
        'circuit_id': race['Circuit']['circuitId'],
        'race_datetime_utc': session_to_utc(race),
        'quali_datetime_utc': session_to_utc(race.get('Qualifying')),
    } for race in schedule])

    return races.sort_values('race_datetime_utc').reset_index(drop=True)


def parse_results(race):
    """One row per driver from a Jolpica results race dict"""
    return [{
        'season': int(race['season']),
        'round': int(race['round']),
        'driver_id': result['Driver']['driverId'],
        'driver_code': result['Driver'].get('code'),
        'constructor_id': result['Constructor']['constructorId'],
        'grid': int(result['grid']),
        'position': int(result['position']),
        'position_text': result['positionText'],
        'points': float(result['points']),
        'status': result['status'],
    } for result in race['Results']]


def parse_qualifying(race):
    """One row per driver from a Jolpica qualifying race dict, Q times in seconds"""
    return [{
        'season': int(race['season']),
        'round': int(race['round']),
        'driver_id': quali['Driver']['driverId'],
        'quali_position': int(quali['position']),
        'q1_s': lap_time_to_seconds(quali.get('Q1')),
        'q2_s': lap_time_to_seconds(quali.get('Q2')),
        'q3_s': lap_time_to_seconds(quali.get('Q3')),
    } for quali in race['QualifyingResults']]


def build_entries(raw_data, races):
    """
    Merge results + qualifying + schedule into one row per driver per race

    Parameters:
    - raw_data: output of collect_raw_data()
    - races: output of parse_schedule()

    Returns:
    - DataFrame sorted by race date, with flags and the y_podium target

    Rules:
    - y_podium = 1 only if the official classification is P1, P2 or P3
      (DNF, DNS and disqualified drivers are rows with y_podium = 0)
    - Disqualified = status text contains 'disqualified' or positionText 'D'
    - Pit-lane start = grid 0 for a driver who did start
    - Missing qualifying row or Q time stays NaN (never 0)
    """
    print("📊 BUILDING ENTRIES TABLE\n")

    results_df = pd.DataFrame([row for race in raw_data['results'].values() for row in parse_results(race)])
    quali_df = pd.DataFrame([row for race in raw_data['qualifying'].values() for row in parse_qualifying(race)])
    print(f"✅ Results rows: {len(results_df):,}")
    print(f"✅ Qualifying rows: {len(quali_df):,}")

    print("\n🔗 Merging on season, round, driver_id...")
    entries = results_df.merge(quali_df, on=['season', 'round', 'driver_id'],
                               how='left', validate='one_to_one', indicator=True)
    entries['has_quali_row'] = entries.pop('_merge') == 'both'

    entries = races.merge(entries, on=['season', 'round'], how='inner', validate='one_to_many')

    # Status flags
    status = entries['status'].str.lower()
    entries['is_classified'] = entries['position_text'].str.isdigit()
    entries['is_dsq'] = status.str.contains('disqualified') | (entries['position_text'] == 'D')
    entries['is_dns'] = status.str.contains('did not start') | (entries['position_text'] == 'W')
    entries['pit_lane_start'] = (entries['grid'] == 0) & ~entries['is_dns']

    # Target
    entries['y_podium'] = (entries['is_classified'] & (entries['position'] <= 3)).astype(int)

    entries = entries.sort_values(['race_datetime_utc', 'position']).reset_index(drop=True)

    print(f"✅ Entries: {len(entries):,} rows | {entries.groupby(['season', 'round']).ngroups} races")
    print(f"✅ Podium rate: {entries['y_podium'].mean():.1%}")

    return entries


# ========================================
# STEP 3: Sanity Checks + Coverage Report
# ========================================

def check_session_dates(races, completed):
    """
    Flag races where qualifying is missing, not before the race, or more than 3 days before

    Known issue: Jolpica session dates were wrong for Las Vegas 2023 and 2024.
    """
    races = races.merge(completed, on=['season', 'round'])
    gap = races['race_datetime_utc'] - races['quali_datetime_utc']
    flagged = races[gap.isna() | (gap <= pd.Timedelta(0)) | (gap > pd.Timedelta(days=3))]

    print("\n📅 SESSION DATE CHECK (qualifying must be 0-3 days before the race)")
    if flagged.empty:
        print("   ✅ No flagged races")
    for _, race in flagged.iterrows():
        print(f"   ⚠️  {race['season']} R{race['round']:2d} {race['race_name']}: "
              f"quali {race['quali_datetime_utc']} | race {race['race_datetime_utc']}")

    vegas = races[races['circuit_id'] == 'vegas']
    print("\n🎰 Las Vegas (known Jolpica date issue):")
    for _, race in vegas.iterrows():
        print(f"   {race['season']} R{race['round']:2d}: quali {race['quali_datetime_utc']} | "
              f"race {race['race_datetime_utc']}")

    return flagged[['season', 'round', 'race_name']].to_dict('records')


def run_sanity_checks(entries, races):
    """
    Run the Phase 1 checks and print a short coverage report

    Parameters:
    - entries: output of build_entries()
    - races: output of parse_schedule()

    Returns:
    - Dict of counts and flagged races (used by write_data_notes)
    """
    print("🔍 SANITY CHECKS\n")

    per_race = entries.groupby(['season', 'round'])
    podiums = per_race['y_podium'].sum()
    drivers = per_race.size()
    q1_missing = per_race['q1_s'].apply(lambda x: x.isna().all())

    report = {
        'rows': len(entries),
        'races': per_race.ngroups,
        'races_not_3_podiums': [f"{s} R{r}" for (s, r), n in podiums.items() if n != 3],
        'drivers_per_race_min': int(drivers.min()),
        'drivers_per_race_max': int(drivers.max()),
        'duplicate_rows': int(entries.duplicated(['season', 'round', 'driver_id']).sum()),
        'missing_quali_rows': int((~entries['has_quali_row']).sum()),
        'races_without_q1_times': [f"{s} R{r}" for (s, r), missing in q1_missing.items() if missing],
        'pit_lane_starts': int(entries['pit_lane_start'].sum()),
        'disqualified': int(entries['is_dsq'].sum()),
        'did_not_start': int(entries['is_dns'].sum()),
        'not_classified': int((~entries['is_classified']).sum()),
        'podium_rate': float(entries['y_podium'].mean()),
    }

    completed = drivers.reset_index()[['season', 'round']]
    report['date_flags'] = check_session_dates(races, completed)

    # Coverage by season
    coverage = entries.groupby('season').agg(
        races=('round', 'nunique'),
        rows=('driver_id', 'size'),
        podium_rows=('y_podium', 'sum'),
        no_quali_row=('has_quali_row', lambda x: (~x).sum()),
        pit_lane=('pit_lane_start', 'sum'),
        dsq=('is_dsq', 'sum'),
        dns=('is_dns', 'sum'),
    )
    print("\n📋 COVERAGE BY SEASON")
    print(coverage.to_string())

    print("\n📊 CHECKS")
    checks = [
        ("Every race has exactly 3 podium rows", not report['races_not_3_podiums'], report['races_not_3_podiums']),
        ("No duplicate driver-race rows", report['duplicate_rows'] == 0, report['duplicate_rows']),
        ("About 20 drivers per race", 18 <= report['drivers_per_race_min'] and report['drivers_per_race_max'] <= 22,
         f"{report['drivers_per_race_min']}-{report['drivers_per_race_max']}"),
    ]
    for label, passed, detail in checks:
        print(f"   {'✅' if passed else '❌'} {label} ({detail})")

    print("\n📌 COUNTED (handled by written rule)")
    print(f"   Missing qualifying rows: {report['missing_quali_rows']}")
    print(f"   Races with no Q1 times:  {report['races_without_q1_times']}")
    print(f"   Pit-lane starts:         {report['pit_lane_starts']}")
    print(f"   Disqualified:            {report['disqualified']}")
    print(f"   Did not start:           {report['did_not_start']}")
    print(f"   Not classified (y=0):    {report['not_classified']}")

    report['passed'] = all(passed for _, passed, _ in checks)
    return report


# ========================================
# STEP 4: Snapshot + Data Notes
# ========================================

def save_snapshot(entries, snapshot_dir):
    """
    Save entries as one versioned parquet snapshot named by last race + content hash

    Returns:
    - (path, hash string)
    """
    row_hashes = pd.util.hash_pandas_object(entries, index=False).values
    data_hash = hashlib.sha256(row_hashes.tobytes()).hexdigest()[:12]

    last = entries.iloc[-1]
    path = Path(snapshot_dir) / f"entries_{last['season']}_R{last['round']:02d}_{data_hash}.parquet"
    entries.to_parquet(path, index=False)

    print(f"💾 Snapshot: {path.name}")
    print(f"   Rows: {len(entries):,} | Hash: {data_hash}")
    return path, data_hash


def write_data_notes(report, snapshot_path, data_hash, notes_path):
    """Write data_notes.md: every known gap and the rule that handles it"""
    date_flags = ', '.join(f"{f['season']} R{f['round']} {f['race_name']}" for f in report['date_flags']) or 'none'

    notes = f"""# Data Notes (Phase 1)

Snapshot: `{Path(snapshot_path).name}` (hash `{data_hash}`)
Rows: {report['rows']:,} | Races: {report['races']} | Podium rate: {report['podium_rate']:.1%}

## Source
- Jolpica (Ergast-compatible) races, results, qualifying. Raw JSON cached per race in `data/raw/`.
- Stable IDs: `driver_id`, `constructor_id`, `circuit_id` (never names or 3-letter codes).
- FastF1 is not used (403 errors in an earlier environment).

## Rules
- **Row and target:** one row per driver per race (from race results). `y_podium = 1` only if
  the official classification is P1, P2 or P3. DNF, DNS and disqualified drivers have `y_podium = 0`.
- **Disqualified:** status text contains "disqualified" or positionText is "D". Count: {report['disqualified']}.
- **Did not start:** status text contains "did not start" or positionText is "W". Count: {report['did_not_start']}.
- **Pit-lane starts:** grid 0 for a driver who did start, flagged `pit_lane_start`. Count: {report['pit_lane_starts']}.
- **Missing qualifying row:** kept with NaN Q times and `has_quali_row = False`. Count: {report['missing_quali_rows']}.
- **Races with no Q1 times:** {report['races_without_q1_times'] or 'none'}. Q times stay NaN, never 0.
- **Cutoff:** `quali_datetime_utc` = the qualifying session that sets the Grand Prix grid.

## Known gaps
- Session date flags (qualifying not 0-3 days before race): {date_flags}.
- Jolpica dates were reported wrong for Las Vegas 2023 and 2024 (see Phase 1 date check output).
- 2022 sprint weekends: the sprint (not qualifying) set the Grand Prix grid. Version 1 ignores
  sprints, so the cutoff for those races is treated as qualifying.
- Drivers who qualified but have no race result row (withdrawn before the race) are not rows.
"""
    Path(notes_path).write_text(notes)
    print(f"📝 Wrote {Path(notes_path).name}")


# ========================================
# STEP 5: Known Date Fixes (Las Vegas 2023, 2024)
# ========================================

# Official timetable, Las Vegas local time is UTC-8:
# 2023: quali Fri 17 Nov 24:00 (= Sat 18 Nov 08:00 UTC), race Sat 18 Nov 22:00 (= Sun 19 Nov 06:00 UTC)
# 2024: quali Fri 22 Nov 22:00 (= Sat 23 Nov 06:00 UTC), race Sat 23 Nov 22:00 (= Sun 24 Nov 06:00 UTC)
# Jolpica has the 2023 qualifying and both 2024 sessions one day early.
KNOWN_DATE_FIXES = {
    (2023, 21): {'quali_datetime_utc': '2023-11-18 08:00', 'race_datetime_utc': '2023-11-19 06:00'},
    (2024, 22): {'quali_datetime_utc': '2024-11-23 06:00', 'race_datetime_utc': '2024-11-24 06:00'},
}

DATE_FIX_NOTE = """
## Date fixes (Phase 1, STEP 5)
- Las Vegas 2023 R21: qualifying 2023-11-17 08:00 UTC -> 2023-11-18 08:00 UTC (race time was correct).
- Las Vegas 2024 R22: qualifying 2024-11-22 06:00 -> 2024-11-23 06:00 UTC, race 2024-11-23 06:00 -> 2024-11-24 06:00 UTC.
- Las Vegas 2025 matched the official timetable, no fix.
- The race order does not change (next races are a week later), so only the cutoff timestamps move.
"""


def apply_date_fixes(races, entries, fixes=KNOWN_DATE_FIXES):
    """
    Replace known-wrong Jolpica session times on both the races and entries tables

    Parameters:
    - races: output of parse_schedule()
    - entries: output of build_entries()
    - fixes: {(season, round): {column: 'YYYY-MM-DD HH:MM' in UTC}}

    Returns:
    - (races, entries) with fixed timestamps, re-sorted by race date
    """
    print("🔧 APPLYING KNOWN DATE FIXES\n")
    races, entries = races.copy(), entries.copy()

    for (season, race_round), fix in fixes.items():
        race_mask = (races['season'] == season) & (races['round'] == race_round)
        entry_mask = (entries['season'] == season) & (entries['round'] == race_round)
        assert race_mask.sum() == 1 and (races.loc[race_mask, 'circuit_id'] == 'vegas').all(), \
            f"{season} R{race_round} is not Las Vegas"

        for column, value in fix.items():
            old = races.loc[race_mask, column].iloc[0]
            new = pd.Timestamp(value, tz='UTC')
            races.loc[race_mask, column] = new
            entries.loc[entry_mask, column] = new
            print(f"   ✅ {season} R{race_round:2d} {column}: {old} → {new}")

    races = races.sort_values('race_datetime_utc').reset_index(drop=True)
    entries = entries.sort_values(['race_datetime_utc', 'position']).reset_index(drop=True)
    return races, entries


def append_data_notes(notes_path, text):
    """Append an extra section to data_notes.md"""
    with open(notes_path, 'a') as notes:
        notes.write(text)
    print(f"📝 Appended to {Path(notes_path).name}")


# ========================================
# PHASE 6: Forward Test Data (refresh + upcoming race)
# ========================================

def refresh_entries(seasons, raw_dir):
    """
    Pull any newly completed races (cached ones are not re-fetched) and rebuild the entries table

    Returns:
    - (races, entries) with known date fixes applied
    """
    raw_data = collect_raw_data(seasons, raw_dir)
    races = parse_schedule(raw_data['schedule'])
    print()
    entries = build_entries(raw_data, races)
    print()
    return apply_date_fixes(races, entries)


def fetch_upcoming_race(season, raw_dir, grid_overrides=None, now=None):
    """
    Find the next race that has not started and build its pre-race rows from Grand Prix qualifying

    Parameters:
    - season: current season
    - raw_dir: raw JSON cache (the schedule is re-fetched, qualifying is cached once published)
    - grid_overrides: {driver_id: grid} for known grid penalties or pit-lane starts (0 = pit lane)
    - now: current time (default: now, UTC)

    Returns:
    - DataFrame, one row per qualifier (empty if qualifying is not published yet)

    Rule: grid = qualifying position. The official starting grid only arrives with the race result,
    so known penalties must be entered in grid_overrides before predicting.
    """
    now = pd.Timestamp(now or pd.Timestamp.now(tz='UTC'))
    payload, _ = fetch_json(f"{JOLPICA_BASE}/{season}/races.json?limit=100",
                            Path(raw_dir) / f"{season}_schedule.json", refresh=True)
    races = parse_schedule(payload['MRData']['RaceTable']['Races'])
    upcoming = races[races['race_datetime_utc'] > now]

    if upcoming.empty:
        print(f"🏁 No upcoming races left in {season}")
        return pd.DataFrame()

    race = upcoming.iloc[0]
    print(f"🏎️  Next race: {race['season']} R{race['round']} {race['race_name']} ({race['circuit_id']})")
    print(f"   Qualifying: {race['quali_datetime_utc']} | Race start: {race['race_datetime_utc']}")

    payload, _ = fetch_json(f"{JOLPICA_BASE}/{season}/{race['round']}/qualifying.json?limit=100",
                            Path(raw_dir) / f"{season}_{race['round']:02d}_qualifying.json")
    quali_table = payload['MRData']['RaceTable']['Races']

    if not quali_table:
        print("   ⏳ Qualifying not published yet, run again after the session")
        return pd.DataFrame()

    quali = pd.DataFrame(parse_qualifying(quali_table[0]))
    drivers = pd.DataFrame([{
        'driver_id': q['Driver']['driverId'],
        'driver_code': q['Driver'].get('code'),
        'constructor_id': q['Constructor']['constructorId'],
    } for q in quali_table[0]['QualifyingResults']])

    upcoming_rows = quali.merge(drivers, on='driver_id', validate='one_to_one')
    for column in ['race_name', 'circuit_id', 'race_datetime_utc', 'quali_datetime_utc']:
        upcoming_rows[column] = race[column]
    upcoming_rows['has_quali_row'] = True
    upcoming_rows['grid'] = upcoming_rows['quali_position'].astype(int)

    for driver_id, grid in (grid_overrides or {}).items():
        assert driver_id in set(upcoming_rows['driver_id']), f"Unknown driver_id in grid_overrides: {driver_id}"
        upcoming_rows.loc[upcoming_rows['driver_id'] == driver_id, 'grid'] = grid
        print(f"   🔧 Grid override: {driver_id} → {'pit lane' if grid == 0 else f'P{grid}'}")

    print(f"   ✅ {len(upcoming_rows)} qualifiers, grid = qualifying position"
          f"{' + overrides' if grid_overrides else ''}")
    return upcoming_rows.sort_values('grid').reset_index(drop=True)


# ========================================
# PHASE 7D: Export Data for the Web App
# ========================================

import shutil


def export_web_data(season, raw_dir, models_dir, out_dir):
    """
    Write everything the web app reads into web/public/data/

    - model.json, parity_fixture.json: copied from artifacts/models (Phase 7B)
    - season.json: calendar (completed flag), current drivers (from the latest race),
      and the default grid (latest qualifying order)

    Parameters:
    - season: current season
    - raw_dir: cached Jolpica JSON (Phase 1)
    - models_dir: artifacts/models
    - out_dir: web/public/data
    """
    raw_dir, out_dir = Path(raw_dir), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"🌐 EXPORTING WEB DATA ({season})\n")

    for name in ['model.json', 'parity_fixture.json']:
        shutil.copy(Path(models_dir) / name, out_dir / name)
        print(f"   ✅ {name}")

    schedule = json.loads((raw_dir / f"{season}_schedule.json").read_text())['MRData']['RaceTable']['Races']
    calendar = [{
        'round': int(race['round']),
        'name': race['raceName'],
        'circuit_id': race['Circuit']['circuitId'],
        'circuit_name': race['Circuit']['circuitName'],
        'locality': race['Circuit']['Location']['locality'],
        'country': race['Circuit']['Location']['country'],
        'race_utc': session_to_utc(race).isoformat(),
        'quali_utc': session_to_utc(race.get('Qualifying')).isoformat(),
        'completed': (raw_dir / f"{season}_{int(race['round']):02d}_results.json").exists(),
    } for race in schedule]

    latest = max(race['round'] for race in calendar if race['completed'])
    results = json.loads((raw_dir / f"{season}_{latest:02d}_results.json").read_text())['MRData']['RaceTable']['Races'][0]
    quali = json.loads((raw_dir / f"{season}_{latest:02d}_qualifying.json").read_text())['MRData']['RaceTable']['Races'][0]

    drivers = [{
        'driver_id': r['Driver']['driverId'],
        'code': r['Driver'].get('code'),
        'number': r['Driver'].get('permanentNumber'),
        'given_name': r['Driver']['givenName'],
        'family_name': r['Driver']['familyName'],
        'nationality': r['Driver'].get('nationality'),
        'constructor_id': r['Constructor']['constructorId'],
        'constructor_name': r['Constructor']['name'],
    } for r in results['Results']]

    # Default grid: latest qualifying order, drivers without a qualifying row go to the back
    quali_order = [q['Driver']['driverId'] for q in sorted(quali['QualifyingResults'], key=lambda q: int(q['position']))]
    field = {d['driver_id'] for d in drivers}
    default_grid = [d for d in quali_order if d in field] + [d for d in field if d not in quali_order]

    season_data = {
        'season': season,
        'exported_at': pd.Timestamp.now(tz='UTC').isoformat(),
        'latest_completed': {'round': latest, 'name': results['raceName']},
        'calendar': calendar,
        'drivers': drivers,
        'default_grid': {'source': f"{season} R{latest} {results['raceName']} qualifying", 'order': default_grid},
    }
    (out_dir / 'season.json').write_text(json.dumps(season_data, indent=2))

    remaining = [race for race in calendar if not race['completed']]
    print(f"   ✅ season.json ({len(calendar)} races, {len(remaining)} remaining, {len(drivers)} drivers)")
    print(f"\n✅ Default grid: {season_data['default_grid']['source']}")
