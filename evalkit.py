# ========================================
# F1 PREDICTOR V4 - evalkit.py
# Phase 2: metrics, race-level bootstrap, expanding-window backtest
# ========================================

from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.metrics import brier_score_loss, log_loss

RACE_KEYS = ['season', 'round']
CALIBRATION_BINS = [0, 0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0]

# Race outcomes: never shown to a model at prediction time
OUTCOME_COLUMNS = ['y_podium', 'position', 'position_text', 'points', 'status',
                   'is_classified', 'is_dsq', 'is_dns', 'pit_lane_start']


# ========================================
# STEP 1: Dev / Holdout Split
# ========================================

def make_split(entries, holdout_size, dev_start):
    """
    Label every race as warmup, dev or holdout (by race date)

    Parameters:
    - entries: Phase 1 entries table
    - holdout_size: last N completed races, opened once in Phase 5
    - dev_start: (season, round) of the first scored dev race; earlier races are warmup (training only)

    Returns:
    - (split_races, entries) where both carry a 'role' column
    """
    split_races = (entries.groupby(RACE_KEYS, as_index=False)
                   .agg(race_name=('race_name', 'first'), race_datetime_utc=('race_datetime_utc', 'first'))
                   .sort_values('race_datetime_utc').reset_index(drop=True))

    race_code = split_races['season'] * 100 + split_races['round']
    split_races['role'] = np.where(race_code >= dev_start[0] * 100 + dev_start[1], 'dev', 'warmup')
    split_races.loc[split_races.index[-holdout_size:], 'role'] = 'holdout'

    print("🔒 DEV / HOLDOUT SPLIT (by race date)\n")
    for role in ['warmup', 'dev', 'holdout']:
        group = split_races[split_races['role'] == role]
        first, last = group.iloc[0], group.iloc[-1]
        print(f"   {role:8s} {len(group):3d} races | {first['season']} R{first['round']:<2d} → "
              f"{last['season']} R{last['round']:<2d}")

    entries = entries.drop(columns='role', errors='ignore').merge(
        split_races[RACE_KEYS + ['role']], on=RACE_KEYS, validate='many_to_one')
    return split_races, entries


# ========================================
# STEP 2: Metrics
# ========================================

def brier_loss(y, p):
    """Row-level squared error"""
    return (np.asarray(p, dtype=float) - np.asarray(y, dtype=float)) ** 2


def log_loss_rows(y, p, eps=1e-15):
    """Row-level log loss (probabilities clipped away from 0 and 1)"""
    y = np.asarray(y, dtype=float)
    p = np.clip(np.asarray(p, dtype=float), eps, 1 - eps)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def brier_score(y, p):
    """Mean squared difference between probability and 0/1 outcome (lower is better)"""
    return float(brier_loss(y, p).mean())


def log_loss_score(y, p):
    """Mean log loss (lower is better)"""
    return float(log_loss_rows(y, p).mean())


def calibration_table(preds, bins=CALIBRATION_BINS):
    """Rows, mean predicted probability and observed podium rate per probability bin"""
    bucket = pd.cut(preds['p'], bins, include_lowest=True).rename('bin')
    return (preds.groupby(bucket, observed=True)
            .agg(rows=('p', 'size'), mean_p=('p', 'mean'), observed=('y_podium', 'mean'))
            .reset_index())


def race_prob_sums(preds):
    """Sum of podium probabilities per race (should be near 3)"""
    return preds.groupby(RACE_KEYS)['p'].sum()


def race_totals(preds, row_loss):
    """Per-race sum of a row-level loss and per-race row count"""
    grouped = pd.Series(np.asarray(row_loss), index=preds.index).groupby(
        [preds['season'], preds['round']])
    return grouped.sum().to_numpy(), grouped.size().to_numpy()


def race_bootstrap(totals, counts, n_boot=2000, seed=42):
    """
    95% interval by resampling whole races (drivers in one race are not independent)

    Returns:
    - (low, high)
    """
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(totals), size=(n_boot, len(totals)))
    stats = totals[idx].sum(axis=1) / counts[idx].sum(axis=1)
    low, high = np.percentile(stats, [2.5, 97.5])
    return float(low), float(high)


def paired_difference(preds_a, preds_b, n_boot=2000, seed=42):
    """
    Brier(A) - Brier(B) on the same rows, with a race-level bootstrap interval
    Negative = A is better.

    Returns:
    - (difference, low, high)
    """
    merged = preds_a.merge(preds_b, on=RACE_KEYS + ['driver_id'], suffixes=('_a', '_b'), validate='one_to_one')
    assert len(merged) == len(preds_a) == len(preds_b), "Models were not scored on the same rows"

    row_diff = brier_loss(merged['y_podium_a'], merged['p_a']) - brier_loss(merged['y_podium_a'], merged['p_b'])
    totals, counts = race_totals(merged, row_diff)
    low, high = race_bootstrap(totals, counts, n_boot, seed)
    return float(totals.sum() / counts.sum()), low, high


def score_predictions(preds, n_boot=2000, seed=42):
    """
    Brier, log loss (with race-level intervals) and per-race probability sums

    Returns:
    - Dict of scores
    """
    brier_totals, counts = race_totals(preds, brier_loss(preds['y_podium'], preds['p']))
    log_totals, _ = race_totals(preds, log_loss_rows(preds['y_podium'], preds['p']))
    sums = race_prob_sums(preds)

    return {
        'model': preds['model'].iloc[0],
        'races': len(counts),
        'rows': int(counts.sum()),
        'brier': brier_totals.sum() / counts.sum(),
        'brier_ci': race_bootstrap(brier_totals, counts, n_boot, seed),
        'log_loss': log_totals.sum() / counts.sum(),
        'log_loss_ci': race_bootstrap(log_totals, counts, n_boot, seed),
        'prob_sum_mean': sums.mean(),
        'prob_sum_min': sums.min(),
        'prob_sum_max': sums.max(),
    }


# ========================================
# STEP 3: Metric Unit Tests (tiny synthetic data)
# ========================================

def run_metric_tests(seed=42):
    """Check every metric on synthetic data with known answers; raises if any test fails"""
    print("🧪 METRIC UNIT TESTS (tiny synthetic data)\n")

    rng = np.random.default_rng(seed)
    y = rng.integers(0, 2, 200)
    p = rng.uniform(0.01, 0.99, 200)
    toy = pd.DataFrame({
        'season': 2000,
        'round': np.repeat(np.arange(10), 20),
        'driver_id': np.tile([f"d{i}" for i in range(20)], 10),
        'y_podium': y,
        'p': p,
        'model': 'toy',
    })

    # Ten identical races → bootstrap interval has zero width
    one_race = toy[toy['round'] == 0]
    identical = pd.concat([one_race.assign(round=r) for r in range(10)], ignore_index=True)
    identical_totals, identical_counts = race_totals(identical, brier_loss(identical['y_podium'], identical['p']))

    toy_score = score_predictions(toy, seed=seed)
    calibration = calibration_table(toy.assign(p=np.where(toy['y_podium'] == 1, 0.9, 0.05)))
    self_diff = paired_difference(toy, toy, seed=seed)

    tests = [
        ("Brier matches sklearn", np.isclose(brier_score(y, p), brier_score_loss(y, p))),
        ("Brier: perfect = 0, coin flip = 0.25",
         brier_score([0, 1], [0, 1]) == 0 and np.isclose(brier_score([0, 1], [0.5, 0.5]), 0.25)),
        ("Log loss matches sklearn", np.isclose(log_loss_score(y, p), log_loss(y, p))),
        ("Race-level Brier equals row-level Brier", np.isclose(toy_score['brier'], brier_score(y, p))),
        ("Probability sums: 20 drivers x 0.15 = 3", np.allclose(race_prob_sums(toy.assign(p=0.15)), 3.0)),
        ("Calibration observed rates (0.0 and 1.0)", calibration['observed'].tolist() == [0.0, 1.0]),
        ("Bootstrap interval contains the estimate",
         toy_score['brier_ci'][0] <= toy_score['brier'] <= toy_score['brier_ci'][1]),
        ("Identical races → zero-width interval",
         np.isclose(*race_bootstrap(identical_totals, identical_counts, seed=seed))),
        ("Model vs itself → difference 0 (0, 0)", np.allclose(self_diff, 0)),
    ]

    for label, passed in tests:
        print(f"   {'✅' if passed else '❌'} {label}")

    assert all(passed for _, passed in tests), "Metric tests failed"
    print(f"\n✅ All {len(tests)} metric tests passed")
    return True


# ========================================
# STEP 4: Expanding-Window Backtest
# ========================================

def backtest(model, table, eval_races, retrain_every=1, save_dir=None, allow_holdout=False):
    """
    Expanding window: train on every earlier race (by date), predict the next one

    Parameters:
    - model: object with .name, .fit(train_df) and .predict_proba(test_df)
    - table: one row per driver per race with a 'role' column (dev rows only until Phase 5)
    - eval_races: races to predict (season, round, race_datetime_utc)
    - retrain_every: refit before every n-th race (1 = before each race)
    - save_dir: folder to save the predictions parquet (optional)
    - allow_holdout: must stay False until Phase 5

    Returns:
    - DataFrame: one prediction per driver per race, with a timestamp
      (.attrs['races_accessed'] lists every race the backtest read)
    """
    if not allow_holdout and (table['role'] == 'holdout').any():
        raise ValueError("🔒 Holdout rows passed to backtest. Pass dev rows only until Phase 5.")

    print(f"🏋️ BACKTEST: {model.name} on {len(eval_races)} races (retrain every {retrain_every})")

    eval_races = eval_races.sort_values('race_datetime_utc').reset_index(drop=True)
    predictions, accessed = [], set()

    for i, race in eval_races.iterrows():
        if i % retrain_every == 0:
            train = table[table['race_datetime_utc'] < race['race_datetime_utc']]
            model.fit(train)
            accessed |= {(int(s), int(r)) for s, r in zip(train['season'], train['round'])}

        test = table[(table['season'] == race['season']) & (table['round'] == race['round'])]
        accessed.add((int(race['season']), int(race['round'])))

        out = test[RACE_KEYS + ['race_name', 'driver_id', 'driver_code', 'grid', 'y_podium']].copy()
        out['p'] = model.predict_proba(test.drop(columns=OUTCOME_COLUMNS, errors='ignore'))
        out['predicted_at'] = pd.Timestamp.now(tz='UTC')
        predictions.append(out)

    preds = pd.concat(predictions, ignore_index=True)
    preds['model'] = model.name
    preds.attrs['races_accessed'] = sorted(accessed)

    if save_dir is not None:
        path = Path(save_dir) / f"dev_{model.name}.parquet"
        preds.to_parquet(path, index=False)
        print(f"   💾 Saved {len(preds):,} predictions → {path.name}")

    return preds


# ========================================
# STEP 5: Results Table + Holdout Access Plot
# ========================================

def compare_models(prediction_sets, baseline='E1_grid_slot', n_boot=2000, seed=42):
    """
    Score every model on the same races, with paired Brier difference vs the baseline

    Returns:
    - DataFrame, one row per model
    """
    by_name = {preds['model'].iloc[0]: preds for preds in prediction_sets}
    rows = []

    for name, preds in by_name.items():
        score = score_predictions(preds, n_boot, seed)
        score['diff_vs_baseline'], low, high = paired_difference(preds, by_name[baseline], n_boot, seed)
        score['diff_ci'] = (low, high)
        rows.append(score)

    results = pd.DataFrame(rows)

    print(f"📊 RESULTS ({results['races'].iloc[0]} races, 95% intervals by race bootstrap)\n")
    print(f"   {'Model':16s} {'Brier':>7s} {'[95% CI]':>17s} {'LogLoss':>8s} {'[95% CI]':>17s} "
          f"{'Δ vs ' + baseline:>18s} {'[95% CI]':>19s} {'Σp per race':>16s}")
    for _, r in results.iterrows():
        print(f"   {r['model']:16s} {r['brier']:7.4f} [{r['brier_ci'][0]:.4f}, {r['brier_ci'][1]:.4f}] "
              f"{r['log_loss']:8.4f} [{r['log_loss_ci'][0]:.4f}, {r['log_loss_ci'][1]:.4f}] "
              f"{r['diff_vs_baseline']:+18.4f} [{r['diff_ci'][0]:+.4f}, {r['diff_ci'][1]:+.4f}] "
              f"{r['prob_sum_mean']:5.2f} ({r['prob_sum_min']:.2f}-{r['prob_sum_max']:.2f})")

    return results


def plot_holdout_access(split_races, prediction_sets, save_path=None):
    """
    Bar per race: was it read (train or predict) by any backtest? Holdout must be empty.

    Returns:
    - Number of holdout races read (must be 0)
    """
    accessed = set().union(*(set(map(tuple, preds.attrs['races_accessed'])) for preds in prediction_sets))
    races = split_races.reset_index(drop=True).copy()
    races['accessed'] = [(s, r) in accessed for s, r in zip(races['season'], races['round'])]

    colors = {'warmup': '#8a8a85', 'dev': '#2a78d6', 'holdout': '#eb6834'}
    fig, ax = plt.subplots(figsize=(12, 3))

    for role in ['warmup', 'dev', 'holdout']:
        group = races[races['role'] == role]
        ax.bar(group.index, group['accessed'].astype(int), width=0.8, color=colors[role],
               label=f"{role}: {group['accessed'].sum()}/{len(group)} races read")
        if role == 'holdout':
            ax.axvspan(group.index.min() - 0.5, group.index.max() + 0.5, color=colors[role], alpha=0.08)

    season_starts = races.groupby('season').head(1)
    ax.set_xticks(season_starts.index, season_starts['season'])
    ax.set_yticks([0, 1], ['not read', 'read'])
    ax.set_xlim(-1, len(races))
    ax.set_title('Races read by Phase 2 backtests (holdout must be empty)', loc='left', color='#333333')
    for side in ['top', 'right']:
        ax.spines[side].set_visible(False)
    ax.legend(loc='upper left', bbox_to_anchor=(0, -0.18), ncol=3, frameon=False)
    fig.tight_layout()

    if save_path is not None:
        fig.savefig(save_path, dpi=120, bbox_inches='tight')
    plt.show()

    holdout_read = int(races.loc[races['role'] == 'holdout', 'accessed'].sum())
    print(f"{'✅' if holdout_read == 0 else '❌'} Holdout races read: {holdout_read}")
    return holdout_read


# ========================================
# PHASE 3: Paired Improvement + Feature Ablation
# ========================================

KEEP_SHARE = 0.90   # keep a group if ≥ 90% of race-bootstrap draws show a lower Brier (set before results)


def paired_improvement(preds_new, preds_ref, n_boot=2000, seed=42):
    """
    Brier(new) - Brier(ref) on the same rows, with race-level bootstrap

    Returns:
    - Dict: diff, ci_low, ci_high, share_below_zero (share of draws where new is better)
    """
    merged = preds_new.merge(preds_ref, on=RACE_KEYS + ['driver_id'], suffixes=('_new', '_ref'),
                             validate='one_to_one')
    assert len(merged) == len(preds_new) == len(preds_ref), "Models were not scored on the same rows"

    row_diff = (brier_loss(merged['y_podium_new'], merged['p_new'])
                - brier_loss(merged['y_podium_new'], merged['p_ref']))
    totals, counts = race_totals(merged, row_diff)

    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(totals), size=(n_boot, len(totals)))
    draws = totals[idx].sum(axis=1) / counts[idx].sum(axis=1)

    return {
        'diff': float(totals.sum() / counts.sum()),
        'ci_low': float(np.percentile(draws, 2.5)),
        'ci_high': float(np.percentile(draws, 97.5)),
        'share_below_zero': float((draws < 0).mean()),
    }


def run_ablation(make_model, table, eval_races, groups, reference_preds,
                 n_boot=2000, seed=42, save_dir=None):
    """
    Add feature groups one at a time (plan order), keep a group only if paired dev Brier improves

    Parameters:
    - make_model: function(feature_columns, name) → model
    - table: dev rows (warmup + dev) with feature columns
    - eval_races: dev races to score
    - groups: {group name: [feature columns]} in the order to try
    - reference_preds: E1 predictions on the same races

    Rule (fixed before results): keep if Brier difference < 0 and ≥ KEEP_SHARE of draws below zero.
    Step 0 fits the same learner with no groups, so gains come from features, not the learner.

    Returns:
    - (ablation DataFrame, kept group names, {model name: predictions})
    """
    print("🧪 FEATURE ABLATION (forward, plan order)\n")
    all_preds = {}

    current = backtest(make_model([], 'E1_logistic'), table, eval_races, save_dir=save_dir)
    all_preds['E1_logistic'] = current
    rows = [{'step': 'learner only (vs E1)', 'model': 'E1_logistic', 'features': 1,
             **paired_improvement(current, reference_preds, n_boot, seed), 'kept': '-'}]

    kept = []
    for group, columns in groups.items():
        name = 'E1_' + '+'.join(g.split('_')[0] for g in kept + [group])
        candidate_columns = [c for g in kept for c in groups[g]] + columns

        preds = backtest(make_model(candidate_columns, name), table, eval_races, save_dir=save_dir)
        all_preds[name] = preds

        result = paired_improvement(preds, current, n_boot, seed)
        keep = result['diff'] < 0 and result['share_below_zero'] >= KEEP_SHARE
        rows.append({'step': f"+ {group}", 'model': name, 'features': 1 + len(candidate_columns),
                     **result, 'kept': 'YES' if keep else 'no'})

        if keep:
            kept.append(group)
            current = preds

    ablation = pd.DataFrame(rows)

    print(f"\n📊 ABLATION TABLE (Δ Brier vs current kept model, negative = better)\n")
    print(f"   {'Step':24s} {'Model':16s} {'#feat':>5s} {'Δ Brier':>9s} {'[95% CI]':>21s} {'P(better)':>9s} {'Kept':>5s}")
    for _, r in ablation.iterrows():
        print(f"   {r['step']:24s} {r['model']:16s} {r['features']:5d} {r['diff']:+9.4f} "
              f"[{r['ci_low']:+.4f}, {r['ci_high']:+.4f}] {r['share_below_zero']:9.0%} {r['kept']:>5s}")

    final_name = current['model'].iloc[0]
    final = paired_improvement(current, reference_preds, n_boot, seed)
    print(f"\n🎯 Final kept model {final_name} vs E1: Δ Brier {final['diff']:+.4f} "
          f"[{final['ci_low']:+.4f}, {final['ci_high']:+.4f}] | P(better) {final['share_below_zero']:.0%}")

    return ablation, kept, all_preds


# ========================================
# PHASE 4: Tuning, Calibration, Sum-to-3 Test, Model Choice
# ========================================

from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

MIN_CALIBRATION_RACES = 10   # races of earlier predictions needed before a calibrator is fitted


def tune_model(make_model, configs, table, eval_races, retrain_every=1, save_dir=None):
    """
    Backtest every config on the dev races, best = lowest dev Brier

    Parameters:
    - make_model: function(config) → model
    - configs: list of parameter dicts (the tuning grid)

    Returns:
    - (tuning DataFrame, best predictions, {model name: predictions})
    """
    rows, all_preds = [], {}

    for config in configs:
        model = make_model(config)
        preds = backtest(model, table, eval_races, retrain_every, save_dir)
        all_preds[model.name] = preds
        rows.append({'model': model.name, **config, 'brier': brier_score(preds['y_podium'], preds['p'])})

    tuning = pd.DataFrame(rows).sort_values('brier').reset_index(drop=True)

    print(f"\n📊 TUNING GRID (dev Brier, lower is better)")
    print(tuning.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print(f"\n✅ Best config: {tuning['model'].iloc[0]}")

    return tuning, all_preds[tuning['model'].iloc[0]], all_preds


def calibrate_expanding(preds, method='platt', min_races=MIN_CALIBRATION_RACES):
    """
    Recalibrate each race with a calibrator fitted on earlier races' out-of-sample predictions only

    Parameters:
    - preds: backtest predictions (in date order)
    - method: 'platt' (logistic on logit p) or 'isotonic' (clipped to [0.001, 0.999])
    - min_races: the first races stay uncalibrated until this many earlier races exist

    Returns:
    - Predictions DataFrame named '<model>+<method>'
    """
    out = preds.copy()
    race_order = preds.groupby(RACE_KEYS, sort=False).ngroup().to_numpy()
    logit = lambda p: np.log(np.clip(p, 1e-4, 1 - 1e-4) / (1 - np.clip(p, 1e-4, 1 - 1e-4))).reshape(-1, 1)

    for i in range(min_races, race_order.max() + 1):
        earlier, current = preds[race_order < i], race_order == i

        if method == 'platt':
            calibrator = LogisticRegression(C=1e6, max_iter=1000).fit(logit(earlier['p'].to_numpy()), earlier['y_podium'])
            out.loc[current, 'p'] = calibrator.predict_proba(logit(preds.loc[current, 'p'].to_numpy()))[:, 1]
        else:
            calibrator = IsotonicRegression(y_min=0.001, y_max=0.999, out_of_bounds='clip')
            calibrator.fit(earlier['p'], earlier['y_podium'])
            out.loc[current, 'p'] = calibrator.predict(preds.loc[current, 'p'])

    out['model'] = f"{preds['model'].iloc[0]}+{method}"
    print(f"🎯 Calibrated {out['model'].iloc[0]} (first {min_races} races left uncalibrated)")
    return out


def rescale_to_three(preds):
    """Scale each race's probabilities so they sum to 3 (capped at 0.999)"""
    out = preds.copy()
    race_sum = out.groupby(RACE_KEYS)['p'].transform('sum')
    out['p'] = (out['p'] * 3 / race_sum).clip(upper=0.999)
    out['model'] = f"{preds['model'].iloc[0]}+sum3"
    return out


def sum_to_three_test(prediction_sets, n_boot=2000, seed=42):
    """
    Does rescaling each race to sum 3 improve Brier? One row per model.

    Returns:
    - (results DataFrame, {rescaled model name: predictions})
    """
    print("⚖️ SUM-TO-3 TEST (Δ Brier after rescaling, negative = better)\n")
    rows, rescaled = [], {}

    for preds in prediction_sets:
        scaled = rescale_to_three(preds)
        rescaled[scaled['model'].iloc[0]] = scaled
        result = paired_improvement(scaled, preds, n_boot, seed)
        rows.append({'model': preds['model'].iloc[0], 'sum_before': race_prob_sums(preds).mean(), **result})
        print(f"   {preds['model'].iloc[0]:24s} Σp {race_prob_sums(preds).mean():.2f} → 3.00 | "
              f"Δ Brier {result['diff']:+.4f} [{result['ci_low']:+.4f}, {result['ci_high']:+.4f}] | "
              f"P(better) {result['share_below_zero']:.0%}")

    return pd.DataFrame(rows), rescaled


def choose_model(results, baseline='E1_grid_slot'):
    """
    Pick the lowest dev Brier. 'Clearly beats' the baseline = whole 95% interval of Δ Brier below zero.

    Returns:
    - (chosen model name, clearly_beats_baseline bool)
    """
    candidates = results[results['model'] != baseline].sort_values('brier')
    best = candidates.iloc[0]
    clearly = best['diff_ci'][1] < 0

    print(f"🏆 Lowest dev Brier: {best['model']} ({best['brier']:.4f})")
    print(f"   Δ vs {baseline}: {best['diff_vs_baseline']:+.4f} [{best['diff_ci'][0]:+.4f}, {best['diff_ci'][1]:+.4f}]")
    print(f"   {'✅ Clearly beats' if clearly else '❌ Does NOT clearly beat'} {baseline} on dev")
    return best['model'], bool(clearly)


# ========================================
# PHASE 5: Final Exam on the Holdout (one shot)
# ========================================

import json

CHAOS_GRID = 7            # chaotic race: a podium finisher started P7 or lower (or from the pit lane)


def unlock_holdout(lock_path, chosen_model, snapshot_hash):
    """
    Open the holdout exactly once, recorded in a lock file

    Re-running is allowed only for the same chosen model (no new choices after seeing holdout results).

    Returns:
    - Lock dict: opened_at, chosen_model, snapshot_hash
    """
    lock_path = Path(lock_path)

    if lock_path.exists():
        lock = json.loads(lock_path.read_text())
        assert lock['chosen_model'] == chosen_model, \
            f"🔒 Holdout was already opened for {lock['chosen_model']}, cannot score a different model"
        print(f"🔓 Holdout already opened at {lock['opened_at']} for {lock['chosen_model']} (re-run, same model)")
    else:
        lock = {'opened_at': pd.Timestamp.now(tz='UTC').isoformat(), 'chosen_model': chosen_model,
                'snapshot_hash': snapshot_hash}
        lock_path.write_text(json.dumps(lock, indent=2))
        print(f"🔓 HOLDOUT UNLOCKED at {lock['opened_at']}")
        print(f"   Chosen model: {chosen_model} | Snapshot: {snapshot_hash}")
        print("   This is the one shot: no model changes after this point.")

    return lock


def save_predictions(preds, save_dir, prefix):
    """Save predictions as <prefix>_<model>.parquet"""
    path = Path(save_dir) / f"{prefix}_{preds['model'].iloc[0]}.parquet"
    preds.to_parquet(path, index=False)
    print(f"   💾 Saved {len(preds):,} predictions → {path.name}")
    return path


def label_chaotic_races(entries):
    """
    Race-level outcome labels for analysis only (never used as features)

    Chaotic = a podium finisher started P7 or lower (or pit lane). Not-classified count is reported only:
    2026 cars retire far more often, so a DNF threshold flagged 86% of 2026 dev races.
    Rule fixed before the holdout was opened.
    """
    podium = entries[entries['y_podium'] == 1]
    from_back = ((podium['grid'] >= CHAOS_GRID) | (podium['grid'] == 0)).groupby(
        [podium['season'], podium['round']]).any()
    not_classified = (~entries['is_classified']).groupby([entries['season'], entries['round']]).sum()

    labels = pd.DataFrame({'podium_from_p7_plus': from_back, 'not_classified': not_classified})
    labels['chaotic'] = labels['podium_from_p7_plus']
    return labels.reset_index()


def per_race_breakdown(preds_model, preds_base, race_labels):
    """
    One row per race: Brier of the model and the baseline, difference, Σp, podium grid slots, chaotic flag
    """
    merged = preds_model.merge(preds_base[RACE_KEYS + ['driver_id', 'p']], on=RACE_KEYS + ['driver_id'],
                               suffixes=('', '_base'), validate='one_to_one')
    merged['sse_model'] = brier_loss(merged['y_podium'], merged['p'])
    merged['sse_base'] = brier_loss(merged['y_podium'], merged['p_base'])

    races = merged.groupby(RACE_KEYS, sort=False).agg(
        race_name=('race_name', 'first'),
        rows=('p', 'size'),
        sse_model=('sse_model', 'sum'),
        sse_base=('sse_base', 'sum'),
        sum_p=('p', 'sum'),
    ).reset_index()
    podium_grids = (merged[merged['y_podium'] == 1].groupby(RACE_KEYS)['grid']
                    .apply(lambda g: '-'.join('PL' if x == 0 else f"P{x}" for x in sorted(g))))

    races['podium_grid'] = [podium_grids.get((s, r), '') for s, r in zip(races['season'], races['round'])]
    races['brier_model'] = races['sse_model'] / races['rows']
    races['brier_base'] = races['sse_base'] / races['rows']
    races['diff'] = races['brier_model'] - races['brier_base']
    return races.merge(race_labels, on=RACE_KEYS, how='left')


def breakdown_by(per_race, column):
    """Brier of model and baseline aggregated over races grouped by a column (e.g., season, chaotic)"""
    grouped = per_race.groupby(column).agg(races=('rows', 'size'), rows=('rows', 'sum'),
                                           sse_model=('sse_model', 'sum'), sse_base=('sse_base', 'sum'))
    grouped['brier_model'] = grouped['sse_model'] / grouped['rows']
    grouped['brier_base'] = grouped['sse_base'] / grouped['rows']
    grouped['diff'] = grouped['brier_model'] - grouped['brier_base']
    return grouped[['races', 'brier_model', 'brier_base', 'diff']].reset_index()


def plot_holdout_results(per_race, preds_model, preds_base, save_path=None):
    """Left: Brier per holdout race (model vs baseline). Right: reliability diagram for both."""
    model_name, base_name = preds_model['model'].iloc[0], preds_base['model'].iloc[0]
    colors = {model_name: '#2a78d6', base_name: '#eb6834'}

    fig, (ax_race, ax_cal) = plt.subplots(1, 2, figsize=(14, 4.5), gridspec_kw={'width_ratios': [2, 1]})

    x = np.arange(len(per_race))
    ax_race.bar(x - 0.21, per_race['brier_model'], width=0.4, color=colors[model_name], label=model_name)
    ax_race.bar(x + 0.21, per_race['brier_base'], width=0.4, color=colors[base_name], label=base_name)
    ax_race.set_xticks(x, [f"R{r}\n{name.replace(' Grand Prix', '')}"
                           for r, name in zip(per_race['round'], per_race['race_name'])], fontsize=8)
    ax_race.set_ylabel('Brier (lower is better)')
    ax_race.set_title('Brier per holdout race', loc='left', color='#333333')
    ax_race.legend(frameon=False)

    ax_cal.plot([0, 1], [0, 1], linestyle='--', color='#b0b0aa', linewidth=1)
    for preds in [preds_model, preds_base]:
        table = calibration_table(preds)
        name = preds['model'].iloc[0]
        ax_cal.plot(table['mean_p'], table['observed'], marker='o', markersize=8, linewidth=2,
                    color=colors[name], label=name)
    ax_cal.set_xlim(0, 1)
    ax_cal.set_ylim(0, 1)
    ax_cal.set_xlabel('Predicted podium probability')
    ax_cal.set_ylabel('Observed podium rate')
    ax_cal.set_title('Calibration on holdout', loc='left', color='#333333')
    ax_cal.legend(frameon=False, loc='upper left')

    for ax in [ax_race, ax_cal]:
        for side in ['top', 'right']:
            ax.spines[side].set_visible(False)
    fig.tight_layout()

    if save_path is not None:
        fig.savefig(save_path, dpi=120, bbox_inches='tight')
    plt.show()


def holdout_decision(results, chosen_model, baseline='E1_grid_slot'):
    """
    Plan rule: the chosen model must beat the baseline on holdout Brier with the interval clear of zero

    Returns:
    - True if the rule is met
    """
    row = results[results['model'] == chosen_model].iloc[0]
    passed = bool(row['diff_ci'][1] < 0)

    print(f"⚖️ DECISION RULE: {chosen_model} must beat {baseline} on holdout Brier, interval clear of zero\n")
    print(f"   Δ Brier {row['diff_vs_baseline']:+.4f} [{row['diff_ci'][0]:+.4f}, {row['diff_ci'][1]:+.4f}]")
    if passed:
        print(f"   ✅ PASSED: {chosen_model} beats {baseline} on the holdout")
    else:
        print(f"   ❌ NOT PASSED: {chosen_model} does not clearly beat {baseline} on the holdout.")
        print("      Honest finding: a grid-slot lookup is hard to beat.")
    return passed


def _score_lines(results):
    """Markdown table rows: model | Brier [CI] | log loss [CI] | Σp"""
    lines = ["| Model | Brier [95% CI] | Log loss [95% CI] | Σp per race (min-max) |", "|---|---|---|---|"]
    for _, r in results.iterrows():
        lines.append(f"| {r['model']} | {r['brier']:.4f} [{r['brier_ci'][0]:.4f}, {r['brier_ci'][1]:.4f}] | "
                     f"{r['log_loss']:.4f} [{r['log_loss_ci'][0]:.4f}, {r['log_loss_ci'][1]:.4f}] | "
                     f"{r['prob_sum_mean']:.2f} ({r['prob_sum_min']:.2f}-{r['prob_sum_max']:.2f}) |")
    return "\n".join(lines)


def _breakdown_lines(table, column):
    """Markdown table rows for breakdown_by() output"""
    lines = [f"| {column} | Races | Model Brier | E1 Brier | Δ |", "|---|---|---|---|---|"]
    for r in table.to_dict('records'):
        lines.append(f"| {r[column]} | {r['races']} | {r['brier_model']:.4f} | {r['brier_base']:.4f} | {r['diff']:+.4f} |")
    return "\n".join(lines)


def write_results_note(path, lock, passed, holdout_results, holdout_improvement, dev_results,
                       per_race, by_season, by_chaos, ablation, model_results, chosen_model):
    """Write results.md: decision, holdout and dev scores, what worked, what did not, where it fails"""
    chosen_dev = model_results[model_results['model'] == chosen_model].iloc[0]
    boosters = model_results[model_results['model'].str.match(r'^(CatBoost|XGBoost)_[^+]*$')]
    best_group = ablation.iloc[1:].sort_values('share_below_zero', ascending=False).iloc[0]
    worst = per_race.sort_values('diff', ascending=False).head(3)
    first, last = per_race.iloc[0], per_race.iloc[-1]

    decision = (f"**PASSED.** {chosen_model} beats E1 on holdout Brier with the interval clear of zero."
                if passed else
                f"**NOT PASSED.** {chosen_model} does not beat E1 on holdout Brier with the interval clear of zero. "
                f"The honest finding is that a grid-slot lookup is hard to beat.")

    worst_lines = "\n".join(
        f"- {r['season']} R{r['round']} {r['race_name']}: Δ {r['diff']:+.4f} (podium from {r['podium_grid']}"
        f"{', chaotic' if r['chaotic'] else ''})" for _, r in worst.iterrows())

    note = f"""# F1 Predictor V4: Results (Phase 5)

Holdout opened once at {lock['opened_at']} | Snapshot `{lock['snapshot_hash']}` | Chosen model: `{chosen_model}`

## Decision
{decision}

Rule (fixed in the plan): the chosen model must beat E1 on holdout Brier with the 95% race-bootstrap
interval clear of zero. Δ Brier = {holdout_improvement['diff']:+.4f}
[{holdout_improvement['ci_low']:+.4f}, {holdout_improvement['ci_high']:+.4f}],
P(better) = {holdout_improvement['share_below_zero']:.0%}. Ten races is a small sample, so the interval is wide.

## Holdout ({first['season']} R{first['round']} to {last['season']} R{last['round']}, {len(per_race)} races)
{_score_lines(holdout_results)}

## Dev (55 races, 2024 R1 to 2026 R7, expanding-window backtest)
{_score_lines(dev_results)}

## What worked
- A leak-proof pipeline: features for every race are identical after deleting later races and poisoning
  the race's own results; a deliberately leaky canary feature was caught in every race.
- The E1 smoothed grid-slot lookup is a very strong baseline (dev Brier {dev_results.iloc[0]['brier']:.4f}).
- Recalibrating E1 with a logistic regression on its logit ({chosen_model}) fixed E1's per-race sums
  (about 2.85 to 3.00) and improved dev Brier by {-chosen_dev['diff_vs_baseline']:.4f}
  [{-chosen_dev['diff_ci'][1]:.4f}, {-chosen_dev['diff_ci'][0]:.4f}].

## What did not work
- None of the four feature groups (qualifying detail, driver form, team strength, circuit history)
  improved paired dev Brier on top of E1. Closest: {best_group['step'][2:]} (P(better) {best_group['share_below_zero']:.0%},
  keep rule needs 90%).
- Boosters on all 13 features were worse than E1 on dev:
{chr(10).join(f"  {r['model']} Δ {r['diff_vs_baseline']:+.4f}, Σp per race {r['prob_sum_min']:.2f}-{r['prob_sum_max']:.2f}" for _, r in boosters.iterrows())}.
  Platt and isotonic calibration did not rescue them.

## Where it fails
Worst holdout races for the chosen model (vs E1):
{worst_lines}

By season (dev + holdout races):
{_breakdown_lines(by_season, 'season')}

Chaotic races (a podium finisher started P{CHAOS_GRID} or lower, or from the pit lane):
{_breakdown_lines(by_chaos, 'chaotic')}

Wet races cannot be split out: there is no verified weather data in version 1 (on the Later list).

## Limitations
- {len(per_race)} holdout races only; intervals are wide.
- V3 as shipped was not scored (it needs FastF1 sessions and its 47-feature pipeline).
- The booster grids were tuned on the same dev races they are reported on (dev numbers slightly optimistic).
- 2022 sprint weekends treat qualifying as the cutoff although the sprint set the grid.
"""
    Path(path).write_text(note)
    print(f"📝 Wrote {Path(path).name}")


# ========================================
# PHASE 6: Forward Test (frozen, timestamped predictions before the race)
# ========================================

def predict_forward(model, train, upcoming, sum_to_three=False):
    """
    Fit on every completed race, predict the upcoming race from its pre-race rows

    Returns:
    - Predictions DataFrame with a predicted_at timestamp
    """
    assert train['race_datetime_utc'].max() < upcoming['race_datetime_utc'].iloc[0], "Training data includes this race"

    model.fit(train)
    preds = upcoming[RACE_KEYS + ['race_name', 'driver_id', 'driver_code', 'grid',
                                  'quali_datetime_utc', 'race_datetime_utc']].copy()
    preds['p'] = model.predict_proba(upcoming)
    preds['model'] = model.name

    if sum_to_three:
        preds = rescale_to_three(preds)
    preds['predicted_at'] = pd.Timestamp.now(tz='UTC')
    return preds


def log_forward_predictions(prediction_sets, log_path):
    """
    Append predictions to the forward log, only before the race starts and only once per race and model

    Returns:
    - The full log DataFrame
    """
    log_path = Path(log_path)
    log = pd.read_parquet(log_path) if log_path.exists() else pd.DataFrame()

    for preds in prediction_sets:
        name, race = preds['model'].iloc[0], preds.iloc[0]
        label = f"{race['season']} R{race['round']} {race['race_name']}"

        if preds['predicted_at'].iloc[0] >= race['race_datetime_utc']:
            raise ValueError(f"❌ {label} has already started, too late to log {name}")
        if not log.empty and ((log['season'] == race['season']) & (log['round'] == race['round'])
                              & (log['model'] == name)).any():
            raise ValueError(f"🔒 {label} already logged for {name}, predictions are frozen")

        log = pd.concat([log, preds], ignore_index=True)
        top3 = preds.nlargest(3, 'p')
        print(f"🔮 {name:18s} {label}: " + " | ".join(f"{r['driver_code']} {r['p']:.0%}" for _, r in top3.iterrows()))

    log.to_parquet(log_path, index=False)
    print(f"\n💾 Logged at {preds['predicted_at'].iloc[0]} → {log_path.name} ({len(log):,} rows)")
    return log


def score_forward_log(log_path, entries, baseline='E1_grid_slot', n_boot=2000, seed=42):
    """
    Score every logged race that now has a result, running score of each model vs the baseline

    Returns:
    - (per-race DataFrame, compare_models results or None)
    """
    log = pd.read_parquet(log_path)
    actual = entries[RACE_KEYS + ['driver_id', 'y_podium']]
    scored = log.merge(actual, on=RACE_KEYS + ['driver_id'], how='inner')

    logged_races = log.groupby(RACE_KEYS, sort=False)['race_name'].first()
    print("📒 FORWARD LOG\n")
    for (season, race_round), race_name in logged_races.items():
        done = ((scored['season'] == season) & (scored['round'] == race_round)).any()
        print(f"   {'✅ scored ' if done else '⏳ pending'} {season} R{race_round} {race_name}")

    if scored.empty:
        print("\n⏳ No logged race has a result yet")
        return pd.DataFrame(), None

    dropped = len(log) - len(scored)
    if dropped:
        print(f"\n   ⚠️  {dropped} logged rows have no race result (e.g., withdrawn) and are not scored")

    per_race = (scored.assign(sse=brier_loss(scored['y_podium'], scored['p']))
                .groupby(RACE_KEYS + ['race_name', 'model'], sort=False)['sse'].mean()
                .unstack('model').reset_index())
    print("\n📋 BRIER PER LOGGED RACE")
    print(per_race.round(4).to_string(index=False))

    print()
    results = compare_models([preds for _, preds in scored.groupby('model', sort=False)],
                             baseline=baseline, n_boot=n_boot, seed=seed)
    return per_race, results


# ========================================
# PHASE 7A: Winner Target + Model Card Helpers
# ========================================

def winner_view(table):
    """
    The same table with 'y_podium' holding the WIN label (official P1), so the whole harness
    (backtest, metrics, bootstrap) scores the winner target unchanged
    """
    view = table.assign(y_podium=(table['is_classified'] & (table['position'] == 1)).astype(int))
    winners = view.groupby(RACE_KEYS)['y_podium'].sum()
    assert (winners == 1).all(), f"Races without exactly one winner: {winners[winners != 1].index.tolist()}"
    return view


def rescale_to_total(preds, total, suffix):
    """Scale each race's probabilities to sum to total (capped at 0.999), model renamed '<model>+<suffix>'"""
    out = preds.copy()
    race_sum = out.groupby(RACE_KEYS)['p'].transform('sum')
    out['p'] = (out['p'] * total / race_sum).clip(upper=0.999)
    out['model'] = f"{preds['model'].iloc[0]}+{suffix}"
    return out


def choose_winner_model(results, baseline='W1_grid_slot', candidate='W1_logistic+sum1'):
    """
    Pre-committed rule (PLAN_V4_AMENDMENT.md): ship the candidate unless its dev Brier is worse than the baseline's

    Returns:
    - Chosen model name
    """
    brier = results.set_index('model')['brier']
    chosen = candidate if brier[candidate] <= brier[baseline] else baseline

    print(f"⚖️ WINNER RULE: ship {candidate} unless its dev Brier is worse than {baseline}\n")
    print(f"   {candidate}: {brier[candidate]:.4f} | {baseline}: {brier[baseline]:.4f}")
    print(f"   ✅ Winner model: {chosen}")
    return chosen


def summarize_result(results, model):
    """One model's scores as a plain dict (for the model card)"""
    r = results[results['model'] == model].iloc[0]
    return {
        'races': int(r['races']),
        'brier': round(float(r['brier']), 4),
        'brier_ci': [round(float(x), 4) for x in r['brier_ci']],
        'baseline_brier': round(float(r['brier'] - r['diff_vs_baseline']), 4),
        'log_loss': round(float(r['log_loss']), 4),
        'diff_vs_baseline': round(float(r['diff_vs_baseline']), 4),
        'diff_ci': [round(float(x), 4) for x in r['diff_ci']],
        'prob_sum_mean': round(float(r['prob_sum_mean']), 3),
    }
