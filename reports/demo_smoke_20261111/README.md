# Local Phase 2 API demo evidence

Captured on 2026-11-11 from local Docker API smoke checks. The initial image was `traffic-queue-api:phase2-audit`; the latest final image is `traffic-queue-api:phase2-final`. The selected model was mounted read-only, the container ran as the non-root `apiuser`, and it was removed after the checks.

Files in this folder record the actual responses:

- `health.json`: service health and whether the model loaded.
- `model_info.json`: model version, target, horizon, model hash, and feature contract.
- `sample_request.json`: safe example request with synthetic input values.
- `sample_prediction.json`: actual prediction response for that request.
- `heldout_positive_sample_request.json` and `heldout_positive_sample_result.json`: API response for the first held-out seed-123 row with a positive future queue and positive prediction. The label is 11.0 m; the prediction is 5.1656688 m (absolute error 5.8343312 m). This is one illustrative row, not an aggregate performance result.

This is local smoke-test evidence only. It does not show a public deployment or real-time Bengaluru traffic data.
