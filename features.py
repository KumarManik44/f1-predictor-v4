# ========================================
# F1 PREDICTOR V4 - features.py
# Phase 3: leak-proof features (only earlier races, sorted by date)
# ========================================

import numpy as np
import pandas as pd

from evalkit import OUTCOME_COLUMNS

KEYS = ['season', 'round', 'driver_id']

# Columns of the race being predicted that are known before it starts
PRE_RACE_COLUMNS = ['season', 'round', 'race_name', 'circuit_id', 'race_datetime_utc', 'quali_datetime_utc',
                    'driver_id', 'driver_code', 'constructor_id', 'grid', 'quali_position',
                    'q1_s', 'q2_s', 'q3_s', 'has_quali_row']

CIRCUIT_PRIOR_STRENGTH = 3   # fixed before results, never tuned

FEATURE_GROUPS = {
    'A_qualifying': ['grid_position', 'quali_gap_to_pole_pct', 'made_q3', 'teammate_quali_gap_pct',
                     'pit_lane_flag', 'quali_missing'],
    'B_driver_form': ['driver_avg_finish_last5', 'driver_podium_rate_last10', 'driver_dnf_rate_last10'],
    'C_team_strength': ['team_avg_finish_last5', 'team_podium_rate_last5'],
    'D_circuit_history': ['driver_circuit_podium_rate', 'driver_circuit_starts'],
}
FEATURE_COLUMNS = [column for columns in FEATURE_GROUPS.values() for column in columns]


# ========================================
# GROUP A: Qualifying (this race, known before the start)
# ========================================

def teammate_gap_pct(race):
    """
    Gap to teammate in percent, on the deepest session both drivers set a time in (Q3, then Q2, then Q1)
    Negative = faster than teammate. NaN if no teammate or no common session.
    """
    gap = pd.Series(np.nan, index=race.index)

    for _, team in race.groupby('constructor_id'):
        if len(team) != 2:
            continue
        a, b = team.index
        for session in ['q3_s', 'q2_s', 'q1_s']:
            time_a, time_b = race.at[a, session], race.at[b, session]
            if pd.notna(time_a) and pd.notna(time_b):
                gap[a] = (time_a - time_b) / time_b * 100
                gap[b] = (time_b - time_a) / time_a * 100
                break

    return gap


def qualifying_features(race):
    """Grid position, gap to pole, made Q3, gap to teammate, pit-lane flag, missing-time flag"""
    best_time = race[['q1_s', 'q2_s', 'q3_s']].min(axis=1)
    pole_time = best_time.min()

    return pd.DataFrame({
        'grid_position': race['grid'].where(race['grid'] > 0).astype(float),   # pit lane → NaN + flag
        'quali_gap_to_pole_pct': (best_time - pole_time) / pole_time * 100,
        'made_q3': race['q3_s'].notna().astype(float).where(race['has_quali_row']),
        'teammate_quali_gap_pct': teammate_gap_pct(race),
        'pit_lane_flag': (race['grid'] == 0).astype(float),
        'quali_missing': best_time.isna().astype(float),
    }, index=race.index)


# ========================================
# GROUP B: Driver Form (earlier races only)
# ========================================

def driver_form_features(race, history):
    """Average finish over last 5 races, podium rate and DNF rate over last 10 (NaN if no history)"""
    by_driver = history.groupby('driver_id')
    last5 = by_driver.tail(5).groupby('driver_id')
    last10 = by_driver.tail(10).groupby('driver_id')

    form = pd.DataFrame({
        'driver_avg_finish_last5': last5['position'].mean(),
        'driver_podium_rate_last10': last10['y_podium'].mean(),
        'driver_dnf_rate_last10': last10['dnf'].mean(),
    })
    return race[['driver_id']].join(form, on='driver_id').drop(columns='driver_id')


# ========================================
# GROUP C: Team Strength (earlier races only)
# ========================================

def team_strength_features(race, history):
    """Team's average finish and podium rate over its last 5 races (both cars)"""
    team_races = (history[['constructor_id', 'race_datetime_utc']].drop_duplicates()
                  .groupby('constructor_id').tail(5))
    recent = history.merge(team_races, on=['constructor_id', 'race_datetime_utc'])

    team = recent.groupby('constructor_id').agg(
        team_avg_finish_last5=('position', 'mean'),
        team_podium_rate_last5=('y_podium', 'mean'),
    )
    return race[['constructor_id']].join(team, on='constructor_id').drop(columns='constructor_id')


# ========================================
# GROUP D: Circuit History (earlier races only)
# ========================================

def circuit_history_features(race, history, prior_strength=CIRCUIT_PRIOR_STRENGTH):
    """
    Driver's podium rate at this circuit, shrunk toward their overall podium rate

    rate = (podiums here + prior_strength * overall rate) / (starts here + prior_strength)
    No earlier starts here → overall rate. No history at all → NaN.
    """
    overall = history.groupby('driver_id')['y_podium'].mean()
    here = (history[history['circuit_id'] == race['circuit_id'].iloc[0]]
            .groupby('driver_id')['y_podium'].agg(['sum', 'count']))

    # Counts: no earlier start at this circuit is a real 0, not a missing value
    podiums = race['driver_id'].map(here['sum']).fillna(0)
    starts = race['driver_id'].map(here['count']).fillna(0)
    overall_rate = race['driver_id'].map(overall)

    return pd.DataFrame({
        'driver_circuit_podium_rate': (podiums + prior_strength * overall_rate) / (starts + prior_strength),
        'driver_circuit_starts': starts.astype(float),
    }, index=race.index)


# ========================================
# BUILD FEATURES (one race at a time, sorted by date)
# ========================================

def build_race_features(entries, season, race_round):
    """
    Features for one race using only races strictly earlier by date

    Parameters:
    - entries: entries table (may contain later races, they are ignored)
    - season, race_round: the race to build features for

    Returns:
    - DataFrame: season, round, driver_id + FEATURE_COLUMNS
    """
    is_race = (entries['season'] == season) & (entries['round'] == race_round)
    race = entries.loc[is_race, PRE_RACE_COLUMNS]   # this race's outcomes are never selected
    race_time = race['race_datetime_utc'].iloc[0]

    history = (entries[entries['race_datetime_utc'] < race_time]
               .sort_values('race_datetime_utc', kind='stable'))
    history = history.assign(dnf=(~history['is_classified']).astype(float))

    return pd.concat([
        race[KEYS],
        qualifying_features(race),
        driver_form_features(race, history),
        team_strength_features(race, history),
        circuit_history_features(race, history),
    ], axis=1)


def build_features(entries):
    """
    Build features for every race and attach them to the entries table

    Returns:
    - entries + FEATURE_COLUMNS (one row per driver per race)
    """
    print(f"🔧 BUILDING FEATURES ({len(FEATURE_COLUMNS)} features in {len(FEATURE_GROUPS)} groups)\n")

    races = entries[['season', 'round', 'race_datetime_utc']].drop_duplicates().sort_values('race_datetime_utc')
    features = pd.concat([build_race_features(entries, season, race_round)
                          for season, race_round in zip(races['season'], races['round'])], ignore_index=True)

    table = entries.merge(features, on=KEYS, how='left', validate='one_to_one')

    for group, columns in FEATURE_GROUPS.items():
        print(f"{group}")
        for column in columns:
            print(f"   ✅ {column:28s} {table[column].notna().mean():6.1%} non-missing")

    print(f"\n✅ Feature table: {len(table):,} rows | {len(races)} races")
    return table


# ========================================
# LEAK TEST (must pass before any model is trained)
# ========================================

# Obviously wrong outcome values written into the race being tested
POISON_VALUES = {'y_podium': 1, 'position': 99, 'points': 999.0, 'position_text': 'LEAK', 'status': 'LEAK',
                 'is_classified': False, 'is_dsq': True, 'is_dns': True, 'pit_lane_start': True}


def run_leak_test(entries, table):
    """
    For every race r: delete every later race, overwrite r's own outcomes with poison values,
    rebuild r's features. They must be identical to the features in the full table.

    A canary (a deliberately leaky feature: driver's podium rate over ALL rows) must be caught.

    Returns:
    - True if no race changed
    """
    assert set(POISON_VALUES) == set(OUTCOME_COLUMNS)
    print("🔒 LEAK TEST (delete later races + poison this race's outcomes)\n")

    races = entries[['season', 'round', 'race_datetime_utc']].drop_duplicates().sort_values('race_datetime_utc')
    failures, canary_caught = [], 0

    for season, race_round, race_time in races.itertuples(index=False):
        truncated = entries[entries['race_datetime_utc'] <= race_time].copy()
        is_race = (truncated['season'] == season) & (truncated['round'] == race_round)
        for column, value in POISON_VALUES.items():
            truncated.loc[is_race, column] = value

        rebuilt = build_race_features(truncated, season, race_round).sort_values('driver_id')
        original = table.loc[(table['season'] == season) & (table['round'] == race_round),
                             KEYS + FEATURE_COLUMNS].sort_values('driver_id')

        same = (rebuilt['driver_id'].tolist() == original['driver_id'].tolist()
                and np.allclose(rebuilt[FEATURE_COLUMNS].to_numpy(float),
                                original[FEATURE_COLUMNS].to_numpy(float), equal_nan=True))
        if not same:
            failures.append(f"{season} R{race_round}")

        # Canary: uses every row it is given, so it must change
        canary_full = entries.groupby('driver_id')['y_podium'].mean()
        canary_cut = truncated.groupby('driver_id')['y_podium'].mean()
        drivers = truncated.loc[is_race, 'driver_id']
        canary_caught += not np.allclose(drivers.map(canary_full), drivers.map(canary_cut), equal_nan=True)

    print(f"   {'✅' if not failures else '❌'} Features unchanged in {len(races) - len(failures)}/{len(races)} races")
    if failures:
        print(f"      Leaking races: {failures}")
    print(f"   {'✅' if canary_caught > 0 else '❌'} Canary (deliberately leaky feature) caught in "
          f"{canary_caught}/{len(races)} races")

    passed = not failures and canary_caught > 0
    print(f"\n{'✅ LEAK TEST PASSED' if passed else '❌ LEAK TEST FAILED'}")
    return passed
