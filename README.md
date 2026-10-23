# 🏎️ F1 Predictor V4

**Race-winner and podium probabilities from the starting grid, built to be honest about what can be predicted.**

Pick any remaining race of the 2026 season, set the starting grid (or load the official qualifying result), and get
every driver's chance of winning and of finishing on the podium. Behind the app is a model built with a leak-proof
pipeline, an untouched holdout, and a written rule for every decision.

![Python](https://img.shields.io/badge/python-3.14-blue.svg)
![React](https://img.shields.io/badge/React-19-61dafb.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)

---

## What it does

| Input | Output |
|---|---|
| The starting grid of a race: positions 1 to 22, plus pit-lane starts | **P(win)** and **P(podium)** for every driver, the predicted winner and the most likely podium |

- Probabilities are coherent: each race's win chances add up to 100%, and podium chances to 300% (three podium places).
- The grid defaults to the latest qualifying order. Drag drivers to reorder them, mark pit-lane starts, or load the
  official qualifying result once it's published.
- The model uses the grid only, so the same grid gives the same odds at every circuit. The race you pick labels the
  prediction; it does not change it. The app says this plainly instead of inventing circuit adjustments.

## Why V4 exists

[V3](https://github.com/KumarManik44/f1-predictor-v3) reported **93.89% accuracy**. Re-reading its code showed that
number meant very little:

- **Accuracy is the wrong metric here.** Only about 15% of drivers finish on the podium, so predicting "no podium" for
  everyone is already about 85% accurate.
- **Features leaked the future.** Team rolling stats were computed on rows sorted by driver, not by date, so a
  teammate's later results could leak into earlier races.
- **"Circuit" features were career totals,** and missing values were filled with 0.
- **The model was chosen and reported on the same small test set,** and the app used hand-tuned multipliers per circuit.

V4 is a clean restart with a fixed contract. **Brier score** is the headline metric (lower is better), every feature is
tested for leaks, a simple baseline sets the bar, and a holdout of 10 races was opened exactly once at the end.

## Results

All scores are out-of-sample: every prediction was made by a model trained only on earlier races (expanding window).
Intervals are 95% bootstrap intervals that resample whole races.

### Podium model: `E1_logistic+sum3`

| Evaluation | Races | Brier | Grid-slot baseline | Δ vs baseline [95% CI] | Verdict |
|---|---|---|---|---|---|
| Development (2024 R1 – 2026 R7) | 55 | **0.0642** | 0.0657 | −0.0016 [−0.0025, −0.0006] | ✅ Better |
| Holdout (2026 R8 – R17, opened once) | 10 | **0.0622** | 0.0626 | −0.0004 [−0.0018, +0.0011] | ≈ Not a clear win |

### Winner model: `W1_logistic+sum1`

| Evaluation | Races | Brier | Grid-slot baseline | Δ vs baseline [95% CI] | Verdict |
|---|---|---|---|---|---|
| Development (2024 R1 – 2026 R7) | 55 | **0.0300** | 0.0305 | −0.0004 [−0.0011, +0.0003] | ≈ Tie |

The winner model has no clean holdout, because the holdout had already been opened once for the podium model.

### What we learned

- **The grid is the signal.** Gap to pole, gap to teammate, driver form, team strength and circuit history were each
  added on top of the grid. None improved the dev Brier (see `artifacts/phase3_ablation.csv`).
- **Bigger models did worse.** CatBoost and XGBoost on all 13 features scored worse than the simple grid-slot lookup.
- **The shipped model is a recalibrated grid lookup.** It is a smoothed podium or win rate per grid slot, passed
  through a logistic recalibration, with each race rescaled to sum to 3 (podium) or 1 (win). It is slightly better than
  the raw lookup on dev and tied it on the holdout. The honest conclusion is that a grid-slot lookup is hard to beat.

## How it works

The notebook [`f1_predcitor_v4_master.ipynb`](f1_predcitor_v4_master.ipynb) follows the plan in
[`Plan/`](Plan/F1_Predictor_V4_Clean_Restart_Plan.pdf) phase by phase. Phase 7 is replaced by
[`PLAN_V4_AMENDMENT.md`](PLAN_V4_AMENDMENT.md). Notebook cells only call functions; the logic lives in four modules.

| Phase | What happens | Key output |
|---|---|---|
| 0 · Setup | Config, pinned library versions | `requirements.txt` |
| 1 · Data | Races, results and qualifying for 2022–2026 from Jolpica, cached per race. One row per driver per race. Known data errors (such as the Las Vegas 2023/2024 session times) are fixed by a written rule. | `data/snapshots/*.parquet`, `data_notes.md` |
| 2 · Harness | Brier, log loss, calibration, per-race sums and race-level bootstrap, all unit-tested. Expanding-window backtest. Baselines E0 (driver podium rate) and E1 (smoothed grid-slot rate). | E1 dev Brier 0.0657 |
| 3 · Features | 13 features in 4 groups, each built only from earlier races. Leak test: rebuild with all later races deleted and the race's own result poisoned; identical in 109/109 races. Forward ablation with a pre-set keep rule. | `features.py`, ablation table |
| 4 · Models | Logistic regression, CatBoost and XGBoost (small grids tuned on dev), Platt and isotonic calibration, sum-to-3 rescaling | `phase4_model_comparison.csv` |
| 5 · Holdout | 10 races opened once, with a lock file so no other model could be scored afterwards | `results.md`, `artifacts/holdout_lock.json` |
| 6 · Forward test | Optional: log frozen predictions after qualifying, score them after the race | `artifacts/predictions/forward_log.parquet` |
| 7 · Ship it | Winner model, final models trained on all 109 races, export, web app | `artifacts/models/`, `web/` |

### Rules that kept it honest

- **Target:** `y = 1` only for an official P1–P3 (or P1 for the winner). Retirements, non-starters and
  disqualifications count as 0.
- **Cutoff:** features may only use races that happened earlier (sorted by date) plus this race's grid.
- **Missing data stays missing:** never filled with 0. Missing qualifying times get an explicit flag.
- **No tuning on the holdout,** and no new ideas mid-phase. Every keep or ship rule was written down before its result
  was seen.

## The web app

A static site in [`web/`](web/) (**Vite, React, TypeScript, Tailwind CSS, Motion, dnd-kit**). There is no server.

- **Inference runs in the browser.** The notebook exports the fitted model as a few numbers (slot rates and logistic
  coefficients) in `web/public/data/model.json`. `web/src/lib/model.ts` applies them exactly like
  `models.predict_from_params` in Python.
- **A parity test checks the two agree.** `npm test` compares browser predictions with Python's for a real race to
  within 1e-12.
- **Live qualifying:** the "Load official qualifying" button fetches the published result from the Jolpica API.
- **Accessibility:** works on phones and desktops, supports keyboard drag (Space to pick up a driver, arrow keys to
  move), honours reduced-motion settings, and never uses colour alone to identify a team.

## Project structure

```
f1-predictor-v4/
├── f1_predcitor_v4_master.ipynb   # The whole pipeline, phase by phase
├── data.py                        # Jolpica collection, cache, entries table, snapshot, web export
├── features.py                    # Leak-proof features + leak test
├── models.py                      # Baselines, learners, final-model export
├── evalkit.py                     # Metrics, bootstrap, backtest, ablation, holdout, forward test
├── requirements.txt
├── Plan/                          # Original V4 plan (PDF)
├── PLAN_V4_AMENDMENT.md           # Phase 7 "Ship it"
├── data_notes.md                  # Every known data gap and how it is handled
├── results.md                     # Phase 5 one-page results note
├── data/
│   ├── raw/                       # Cached Jolpica JSON (re-runs make no API calls)
│   └── snapshots/                 # Versioned parquet snapshots (named by content hash)
├── artifacts/
│   ├── models/                    # podium_model.pkl, winner_model.pkl, model.json, parity_fixture.json
│   ├── predictions/               # Every backtest prediction, timestamped
│   └── *.csv, *.png               # Ablation, model comparison, holdout plots
└── web/                           # The web app (React + TypeScript)
    ├── public/data/               # model.json, season.json, parity_fixture.json (exported by the notebook)
    └── src/
```

## Run it yourself

**Notebook** (Python 3.14, pinned versions in `requirements.txt`):

```bash
pip install -r requirements.txt
jupyter notebook f1_predcitor_v4_master.ipynb
```

Run the cells top to bottom. Phase 5 refuses to score a different model once `artifacts/holdout_lock.json` exists.

**Web app** (Node 20+):

```bash
cd web
npm install
npm run dev      # local dev server
npm test         # browser-vs-Python parity test
npm run build    # static build in web/dist
```

### Updating after a race

1. Re-run Phase 1 (STEP 1–5) to pull the new results. Cached races are not fetched again.
2. Re-run 7B (train and save the final models) and 7D (export the web data).
3. Commit and push.

## Limitations

- **Ten holdout races is a small sample,** so the intervals are wide.
- **Grid only.** Weather, tyre strategy, safety cars and reliability are not modelled, so chaotic races (a podium from
  P7 or lower) are where the model does worst.
- **The official starting grid only appears with the race result.** Before the race, the grid is the qualifying order
  plus any penalties you apply yourself.
- **Sprint weekends:** the Grand Prix qualifying session is treated as the cutoff. In 2022 the sprint set the grid.

## Data & credits

Race data from [Jolpica](https://github.com/jolpica/jolpica-f1), the community-run successor to the Ergast API.

This is an independent project. It is not affiliated with, endorsed by, or connected to Formula 1, the FIA, or any
Formula 1 team. F1 and related marks belong to their respective owners.

## License

[MIT](LICENSE) © 2026 Kumar Manik
