# Member 2 — Phase 1 Model Report

## Current traffic-volume baseline

The current task is regression on same-day daily `Traffic Volume`; its unit is unspecified in the reviewed documentation. It is not a queue-length model and does not predict five minutes ahead.

The trainer uses `Area Name`, `Road/Intersection Name`, and `Weather Conditions` as categorical inputs, plus `day_of_week`, `month`, `is_weekend`, `is_holiday`, `is_event_day`, and `roadwork_flag` as numeric inputs. `Date` determines the chronological split but is not a model input. `weekday_flag` is excluded because it duplicates `is_weekend`. One-hot encoding is fitted within each training partition; unseen category labels are ignored.

The compared methods are a training-mean predictor, Linear Regression, Random Forest (200 trees, maximum depth 12), and XGBoost (300 trees, maximum depth 6, learning rate 0.05). The code reports an 80/20 random row split with seed 42 as a comparison, and uses the latest 20% of distinct dates as the primary chronological test split.

| Chronological split | RMSE | MAE | R² |
|---|---:|---:|---:|
| Mean baseline | 12846.2 | 10544.0 | -0.000 |
| Linear Regression | 10454.1 | 8499.3 | 0.338 |
| Random Forest | 10965.4 | 8808.5 | 0.271 |
| XGBoost | 10964.8 | 8831.6 | 0.271 |

The reproduced split trained on 2022-01-01 through 2024-01-31 (7,145 rows, 761 dates) and tested on 2024-02-01 through 2024-08-09 (1,791 rows, 191 dates). RMSE is the square root of mean squared error; MAE is mean absolute error; R² is the coefficient of determination. RMSE and MAE use the target's unspecified unit; R² is unitless.

## Reproduction evidence and scope

The successful run used the adopted local feature and training source in the isolated sibling scratch copy at `../phase1-baseline-repro/project`, using Python 3.12.6 and the pinned key versions: pandas 2.3.3, NumPy 2.2.6, scikit-learn 1.7.2, XGBoost 3.2.0, joblib 1.6.0, holidays 0.105, and MLflow 3.16.1. The scratch feature output had 8,936 rows, 12 columns, no missing values, and a numeric, finite, nonnegative target. The adopted local baseline report lists Python 3.14.0 and scikit-learn 1.8.0. Scratch metrics matched that local implementation's report at displayed precision; they do not reproduce the different legacy metrics in the pre-adoption GitHub clone. The `python -m src.models.train` command completed with exit code 0; its model loaded and produced 32 finite predictions, and six MLflow runs finished. The execution output and scratch report are available evidence; no separate console-log file was saved. The original report and original model artifacts were not regenerated.

The training code selects its champion by lowest RMSE on the chronological test split. This uses the test set for model selection and can make the reported winner optimistic. Future work should use a separate validation set for model selection and keep a final chronological test set untouched until evaluation.

## Focused unit-test evidence

Five unit tests passed in the isolated test-only copy using Python 3.12.6 and `python -m unittest discover -s tests -v`. The three feature tests check blank required-category rejection, the expected output interface with IQR candidates retained, and repeatable output. The two training-helper tests check handling of unseen categories and that each date stays in one time-split partition. These are focused unit tests, not end-to-end data, full-training, artifact, MLflow, or SUMO tests.

This report describes the Phase 1 historical daily Traffic Volume baseline only. A separate Phase 2 SUMO workflow now predicts simulated queue length 60 seconds ahead and evaluates controllers; its model, metrics, and limitations are documented in `docs/queue_prediction_evaluation_plan.md` and `docs/phase2_handoff_summary.md`. The two targets and their metrics must not be combined.
