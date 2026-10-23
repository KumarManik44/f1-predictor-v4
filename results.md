# F1 Predictor V4: Results (Phase 5)

Holdout opened once at 2026-10-23T15:09:12.817690+00:00 | Snapshot `68ee1ec64f65` | Chosen model: `E1_logistic+sum3`

## Decision
**NOT PASSED.** E1_logistic+sum3 does not beat E1 on holdout Brier with the interval clear of zero. The honest finding is that a grid-slot lookup is hard to beat.

Rule (fixed in the plan): the chosen model must beat E1 on holdout Brier with the 95% race-bootstrap
interval clear of zero. Δ Brier = -0.0004
[-0.0018, +0.0011],
P(better) = 70%. Ten races is a small sample, so the interval is wide.

## Holdout (2026 R8 to 2026 R17, 10 races)
| Model | Brier [95% CI] | Log loss [95% CI] | Σp per race (min-max) |
|---|---|---|---|
| E1_grid_slot | 0.0626 [0.0455, 0.0822] | 0.2101 [0.1559, 0.2775] | 2.92 (2.92-2.92) |
| E1_logistic+sum3 | 0.0622 [0.0436, 0.0832] | 0.2088 [0.1497, 0.2824] | 3.00 (3.00-3.00) |

## Dev (55 races, 2024 R1 to 2026 R7, expanding-window backtest)
| Model | Brier [95% CI] | Log loss [95% CI] | Σp per race (min-max) |
|---|---|---|---|
| E1_grid_slot | 0.0657 [0.0583, 0.0733] | 0.2189 [0.1957, 0.2445] | 2.85 (2.78-2.92) |
| E1_logistic+sum3 | 0.0642 [0.0559, 0.0726] | 0.2142 [0.1876, 0.2435] | 3.00 (3.00-3.00) |

## What worked
- A leak-proof pipeline: features for every race are identical after deleting later races and poisoning
  the race's own results; a deliberately leaky canary feature was caught in every race.
- The E1 smoothed grid-slot lookup is a very strong baseline (dev Brier 0.0657).
- Recalibrating E1 with a logistic regression on its logit (E1_logistic+sum3) fixed E1's per-race sums
  (about 2.85 to 3.00) and improved dev Brier by 0.0016
  [0.0006, 0.0025].

## What did not work
- None of the four feature groups (qualifying detail, driver form, team strength, circuit history)
  improved paired dev Brier on top of E1. Closest: C_team_strength (P(better) 67%,
  keep rule needs 90%).
- Boosters on all 13 features were worse than E1 on dev:
  CatBoost_d4_lr0.03 Δ +0.0024, Σp per race 2.06-4.24
  XGBoost_d3_lr0.03 Δ +0.0055, Σp per race 1.18-4.57.
  Platt and isotonic calibration did not rescue them.

## Where it fails
Worst holdout races for the chosen model (vs E1):
- 2026 R13 Italian Grand Prix: Δ +0.0036 (podium from P2-P5-P19, chaotic)
- 2026 R11 Hungarian Grand Prix: Δ +0.0023 (podium from P1-P4-P7, chaotic)
- 2026 R15 Azerbaijan Grand Prix: Δ +0.0021 (podium from P1-P4-P8, chaotic)

By season (dev + holdout races):
| season | Races | Model Brier | E1 Brier | Δ |
|---|---|---|---|---|
| 2024 | 24 | 0.0694 | 0.0712 | -0.0018 |
| 2025 | 24 | 0.0591 | 0.0609 | -0.0018 |
| 2026 | 17 | 0.0628 | 0.0632 | -0.0003 |

Chaotic races (a podium finisher started P7 or lower, or from the pit lane):
| chaotic | Races | Model Brier | E1 Brier | Δ |
|---|---|---|---|---|
| False | 52 | 0.0528 | 0.0553 | -0.0025 |
| True | 13 | 0.1077 | 0.1047 | +0.0030 |

Wet races cannot be split out: there is no verified weather data in version 1 (on the Later list).

## Limitations
- 10 holdout races only; intervals are wide.
- V3 as shipped was not scored (it needs FastF1 sessions and its 47-feature pipeline).
- The booster grids were tuned on the same dev races they are reported on (dev numbers slightly optimistic).
- 2022 sprint weekends treat qualifying as the cutoff although the sprint set the grid.
