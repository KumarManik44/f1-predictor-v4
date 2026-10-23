# ========================================
# F1 PREDICTOR V4 - models.py
# Phase 2/4: baselines (E0, E1), logistic regression, CatBoost, XGBoost
# ========================================

import numpy as np
import pandas as pd


# ========================================
# BASELINES (defined before any results, never tuned)
# Every model has: .name, .fit(train_df), .predict_proba(test_df)
# ========================================

def grid_slot(grid):
    """
    Grid slot bucket for E1

    - 1 to 10: own slot ('1' ... '10')
    - 11 and below: pooled as '11+'
    - 0: pit-lane start ('pit')
    """
    grid = pd.Series(grid)
    slots = np.where(grid == 0, 'pit', np.where(grid <= 10, grid.astype(str), '11+'))
    return pd.Series(slots, index=grid.index)


class DriverRateBaseline:
    """
    E0: historical podium rate per driver (all earlier races)
    Drivers with no history get the overall podium rate.
    """
    name = 'E0_driver_rate'

    def fit(self, train):
        self.base_rate = train['y_podium'].mean()
        self.rates = train.groupby('driver_id')['y_podium'].mean()
        return self

    def predict_proba(self, test):
        return test['driver_id'].map(self.rates).fillna(self.base_rate).to_numpy(dtype=float)


class GridSlotBaseline:
    """
    E1: smoothed grid-slot podium rate

    rate(slot) = (podiums + prior_strength * base_rate) / (starts + prior_strength)
    prior_strength is fixed at 10 (set before seeing results, never tuned).
    """
    name = 'E1_grid_slot'

    def __init__(self, prior_strength=10):
        self.prior_strength = prior_strength

    def fit(self, train):
        self.base_rate = train['y_podium'].mean()
        stats = train.groupby(grid_slot(train['grid']))['y_podium'].agg(['sum', 'count'])
        self.rates = (stats['sum'] + self.prior_strength * self.base_rate) / (stats['count'] + self.prior_strength)
        return self

    def predict_proba(self, test):
        return grid_slot(test['grid']).map(self.rates).fillna(self.base_rate).to_numpy(dtype=float)


# ========================================
# ABLATION LEARNER (Phase 3): E1 + feature groups
# ========================================

from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


class E1PlusLogistic:
    """
    Logistic regression on logit(E1 probability) + extra feature columns

    - E1 is refit on each training window, then its logit is the first input
    - Missing values: median imputation + an explicit missing-indicator column (never 0)
    - C fixed at 1.0 (not tuned in Phase 3)
    """

    def __init__(self, feature_columns, name, C=1.0):
        self.feature_columns = list(feature_columns)
        self.name = name
        self.C = C

    def design_matrix(self, df):
        p = np.clip(self.e1.predict_proba(df), 1e-4, 1 - 1e-4)
        X = df[self.feature_columns].astype(float).copy()
        X.insert(0, 'e1_logit', np.log(p / (1 - p)))
        return X

    def fit(self, train):
        self.e1 = GridSlotBaseline().fit(train)
        self.pipeline = make_pipeline(
            SimpleImputer(strategy='median', add_indicator=True),
            StandardScaler(),
            LogisticRegression(C=self.C, max_iter=2000),
        )
        self.pipeline.fit(self.design_matrix(train), train['y_podium'])
        return self

    def predict_proba(self, test):
        return self.pipeline.predict_proba(self.design_matrix(test))[:, 1]


# ========================================
# PHASE 4: Boosters (NaN stays NaN, small grid tuned on dev races only)
# ========================================

from catboost import CatBoostClassifier
from xgboost import XGBClassifier

CATBOOST_GRID = [{'depth': depth, 'learning_rate': lr} for depth in [4, 6] for lr in [0.03, 0.1]]
XGBOOST_GRID = [{'max_depth': depth, 'learning_rate': lr} for depth in [3, 5] for lr in [0.03, 0.1]]


class BoosterModel:
    """
    Gradient-boosted trees on the raw feature columns

    - kind: 'CatBoost' or 'XGBoost'
    - params: one config from CATBOOST_GRID / XGBOOST_GRID
    - Missing values are passed as NaN (both libraries handle them natively)
    """

    def __init__(self, kind, params, feature_columns, seed=42):
        self.kind = kind
        self.params = params
        self.feature_columns = list(feature_columns)
        self.seed = seed
        depth = params.get('depth', params.get('max_depth'))
        self.name = f"{kind}_d{depth}_lr{params['learning_rate']}"

    def make_estimator(self):
        if self.kind == 'CatBoost':
            return CatBoostClassifier(iterations=300, l2_leaf_reg=3, random_seed=self.seed,
                                      verbose=0, thread_count=-1, **self.params)
        return XGBClassifier(n_estimators=300, subsample=0.8, colsample_bytree=0.8, min_child_weight=3,
                             random_state=self.seed, n_jobs=-1, eval_metric='logloss', **self.params)

    def fit(self, train):
        self.estimator = self.make_estimator()
        self.estimator.fit(train[self.feature_columns].astype(float), train['y_podium'])
        return self

    def predict_proba(self, test):
        return self.estimator.predict_proba(test[self.feature_columns].astype(float))[:, 1]


# ========================================
# PHASE 7A: Winner Model (same construction as the podium model)
# The harness scores the 'y_podium' column, so winner models are fit and scored on a
# winner view of the table where that column holds the win label (evalkit.winner_view)
# ========================================

class WinnerGridSlotBaseline(GridSlotBaseline):
    """W1: smoothed grid-slot win rate (same slots and prior strength as E1)"""
    name = 'W1_grid_slot'


# ========================================
# PHASE 7B: Final Models + Export (pickle for Python, JSON parameters for the web app)
# ========================================

import json
import pickle
from pathlib import Path

P_CAP = 0.999        # per-driver cap after rescaling, same as evalkit.rescale_to_three
LOGIT_CLIP = 1e-4    # same clip as E1PlusLogistic.design_matrix


def export_params(model, race_total):
    """
    The fitted grid-only model as plain numbers

    p = sigmoid(intercept + coef * (logit(slot_rate) - scaler_mean) / scaler_scale),
    then each race is rescaled to sum to race_total and capped at P_CAP.
    """
    scaler, logistic = model.pipeline[-2], model.pipeline[-1]
    assert logistic.coef_.shape == (1, 1), "Expected a grid-only model (one input: E1 logit)"

    return {
        'model': model.name,
        'slot_rates': {slot: float(rate) for slot, rate in model.e1.rates.items()},
        'base_rate': float(model.e1.base_rate),
        'logit_clip': LOGIT_CLIP,
        'scaler_mean': float(scaler.mean_[0]),
        'scaler_scale': float(scaler.scale_[0]),
        'coef': float(logistic.coef_[0, 0]),
        'intercept': float(logistic.intercept_[0]),
        'race_total': race_total,
        'p_cap': P_CAP,
    }


def predict_from_params(params, grid):
    """
    Reference implementation of an exported model for one race (the web app mirrors this exactly)

    Parameters:
    - params: output of export_params()
    - grid: starting grid slot per driver for the whole field (0 = pit lane)

    Returns:
    - Array of probabilities, summing to race_total (before the cap)
    """
    rate = grid_slot(pd.Series(grid)).map(params['slot_rates']).fillna(params['base_rate']).to_numpy(dtype=float)
    rate = np.clip(rate, params['logit_clip'], 1 - params['logit_clip'])
    z = (np.log(rate / (1 - rate)) - params['scaler_mean']) / params['scaler_scale']
    p = 1 / (1 + np.exp(-(params['intercept'] + params['coef'] * z)))
    return np.minimum(p * params['race_total'] / p.sum(), params['p_cap'])


def check_export_parity(model, params, table):
    """
    The exported parameters must reproduce the fitted model on every race in the table

    Returns:
    - Largest absolute difference across all races
    """
    worst = 0.0
    for _, race in table.groupby(['season', 'round']):
        p_model = model.predict_proba(race)
        p_model = np.minimum(p_model * params['race_total'] / p_model.sum(), params['p_cap'])
        worst = max(worst, float(np.abs(p_model - predict_from_params(params, race['grid'])).max()))
    return worst


def save_final_models(final_models, exported, card, out_dir, fixture=None):
    """
    Save pickles (like V3) and one model.json for the web app

    Parameters:
    - final_models: {'podium': model, 'winner': model}
    - exported: {'podium': params, 'winner': params}
    - card: model card dict (scores, data, versions)
    - out_dir: artifacts/models
    - fixture: optional {grid, expected probabilities} for the web app parity test
    """
    out_dir = Path(out_dir)
    print("💾 SAVING FINAL MODELS\n")

    for target, model in final_models.items():
        path = out_dir / f"{target}_model.pkl"
        with open(path, 'wb') as f:
            pickle.dump(model, f)
        print(f"   ✅ {path.name:24s} ({model.name})")

    (out_dir / 'model.json').write_text(json.dumps({**exported, 'card': card}, indent=2, default=str))
    print(f"   ✅ {'model.json':24s} (parameters + model card for the web app)")

    if fixture is not None:
        (out_dir / 'parity_fixture.json').write_text(json.dumps(fixture, indent=2, default=str))
        print(f"   ✅ {'parity_fixture.json':24s} (one race, Python predictions to match in the browser)")
