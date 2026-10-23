# F1 Predictor V4: Plan Amendment

Written 2026-10-23, after Phase 5. It replaces **Phase 7** of `Plan/F1_Predictor_V4_Clean_Restart_Plan.pdf`.
Phases 0 to 6 and the rules (the contract) stay unchanged.

## Why
- Phase 5 result: `E1_logistic+sum3` tied E1 on the holdout. Δ Brier was −0.0004 [−0.0018, +0.0011], so it was
  NOT PASSED. The original plan said to build `predict_race()` only on a real lift.
- New goal: ship V4 as a GitHub repo plus a polished web app that predicts from qualifying results.
  It must also be honest about what the model can and cannot do.

## Decisions (made 2026-10-23)
| Topic | Decision |
|---|---|
| Targets | P(podium), as validated, plus P(win), as new |
| Podium model | `E1_logistic+sum3`, the Phase 4 choice (tied E1 on holdout, and the app says so) |
| Winner model | Built the same way: W1 grid-slot win rate, then logistic recalibration, then each race rescaled to sum to 1 |
| Headline metric | Brier vs the grid-slot baseline. Never accuracy |
| Frontend | Static web app: Vite + React + TypeScript + Tailwind + Framer Motion (replaces Streamlit, 2026-10-23) |
| Inference | In the browser. Python exports the fitted model parameters to `model.json`, and TypeScript applies them |
| Data in app | V3-style: pick any remaining race and set the grid yourself. The grid defaults to the latest qualifying order and is edited by drag or select. Optional "Load official qualifying" button (Jolpica, CORS allowed) once it is published |
| Automation | None (2026-10-23). Models are trained and saved from the notebook, then deployed, like V3 |
| Hosting | GitHub Pages, deployed by GitHub Actions. No backend |
| Repo | New `f1-predictor-v4`. Created and pushed only after explicit approval |

## Rules added
- **Winner model, pre-committed:** the shipped winner model is `W1_logistic+sum1` unless its dev Brier is worse than
  W1's, in which case it is W1. Nothing is tuned. Buckets, prior strength (10) and learner settings mirror the podium model.
- **Winner model has no clean holdout:** the holdout was opened once for the podium model. P(win) is judged on the
  55 dev races (expanding window) and in the Phase 6 forward test. The app labels it that way.
- **Grid input:** the grid is the qualifying position plus announced penalties and pit-lane starts (editable in the app).
  The official starting grid only arrives with the race result.
- **No hand-tuned adjustments:** no circuit multipliers, form boosts or hard-coded standings, and no fillna(0).
- **Layout:** the notebook and its four .py files stay the source of truth. The web app (`web/`) only reads exported
  JSON and never retrains.
- **Parity:** the browser predictions must match Python's to 1e-9 on a saved fixture race (an automated test).

## PHASE 7 | Ship it (replaces the original Phase 7)

### 7A. Winner model (dev evaluation)
- **Steps:** target `y_win` = official P1. Build W1 (smoothed grid-slot win rate: slots 1 to 10, 11+ pooled, pit lane
  separate) and `W1_logistic+sum1`. Backtest both on the 55 dev races. Report Brier, log loss, calibration and the
  per-race sum (should be near 1), all with race-bootstrap intervals.
- **Output:** a winner results table on dev.
- **Done when:** the pre-committed rule above has picked the winner model, with evidence printed.

### 7B. Final models + export for the web app
- **Steps:** fit the podium and winner models on every completed race. Save them to `artifacts/models/` and export
  `web/public/data/model.json`. That file holds the slot rates and logistic coefficients for both targets, plus a model
  card listing the model name, target, trained-through race, snapshot hash, library versions, dev and holdout scores,
  and the forward-test score so far. Also export `calendar.json`, `drivers.json` (codes, teams, colours), the latest
  qualifying snapshot, the forward log, and one fixture race with Python's predictions.
- **Output:** saved models plus the JSON files in `web/public/data/`.
- **Done when:** a fresh kernel reproduces the notebook's predictions for one race exactly from the saved files.

### 7C. predict_race() (deferred: the browser does this from model.json, `models.predict_from_params` is the Python reference)
- **Steps:** `predict_race(season, round, grid_overrides=None)` fetches Grand Prix qualifying from Jolpica (cached)
  for any round. It returns the full field (all qualifiers, not only the top 10): driver, team, grid, P(win),
  P(podium), the predicted winner and the predicted top 3. A clear message is shown if qualifying is not published yet.
- **Output:** `predict_race()` plus a saved example output (Austin 2026 R18 once qualifying is out).
- **Done when:** it runs for a past race and matches the backtest predictions for that race.

### 7D. Web app (`web/`)
- **Steps:**
  - Race selector: any remaining race of the current season (like V3).
  - A starting-grid view laid out like the real grid (staggered pairs). The full field defaults to the latest
    qualifying order. Drag drivers or pick from selects to set the grid; probabilities recompute and animate. A
    "Load official qualifying" button appears once Jolpica publishes it.
  - Honesty note: the model uses the grid only, so the same grid gives the same probabilities at every circuit.
    The race choice labels the prediction, it does not change it.
  - Results: winner card, top-3 podium and full-field probability bars (P(win), P(podium)) in team colours.
  - Track record: the forward-test log, with E1 vs the chosen model per race.
  - A model card with Brier vs the grid baseline on dev and holdout, and a plain-language note that the model is a
    recalibrated grid lookup that did not beat E1 on holdout.
  - Responsive (phone to desktop), dark theme, accessible (keyboard alternative to drag, labels never colour-only).
- **Output:** `web/`, which runs locally with `npm run dev`. A TypeScript parity test runs against the Python fixture.
- **Done when:** the parity test passes, and the app runs locally for a past race and for the next race.

### 7E. Repo + deploy
- **Steps:**
  - Repo layout: notebook, the four .py files, `app.py`, `requirements.txt`, the data snapshot, the saved models,
    `results.md`, `data_notes.md`, this amendment, `README.md` (honest metrics, method, limitations) and an MIT `LICENSE`.
  - A GitHub Actions workflow builds `web/` and deploys it to GitHub Pages on every push to main.
  - Create the GitHub repo and push (only after approval, and confirm which GitHub account: the V3 repo is under
    KumarManik44, while the CLI here is logged in as kumar-growthx).
- **Output:** a public repo and a live app URL.
- **Done when:** the live app predicts the next race from its qualifying results.

## Weekly routine after shipping (continues Phase 6)
Manual, like V3: when you want fresher models, re-run the notebook (Phase 1 refresh → 7B) and push. Pages redeploys
itself. Phase 6 forward logging stays optional (notebook STEP 2 after qualifying). Automation is not planned.
