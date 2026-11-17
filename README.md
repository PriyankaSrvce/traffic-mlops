# Model artifact: bengaluru queue hurdle model v2 (drift-retrained)

- File: `bengaluru_queue_hurdle_v1_2026-11.joblib` (the evaluator's family name; registry name "v2 hurdle (drift-retrained)")
- SHA-256: `8da60b0e70a0e38c3e4c5d82eefd47fd170949997e62b9bbf3f573ebb03c0804`
- Produced by Metaflow `BengaluruQueueModelFlow` run 3 (reproduced bit-for-bit by runs 4 and 5)
- Training data SHA-256: `177130ea8b0622fd0575d9b2cb3a4c899a522a6e4fb3f02242defefb82fd93c4` (607,924 rows, 30 SUMO runs)
- Registry: `registry/model_versions.json` on `main`

The serving container downloads this file over HTTPS and refuses to start unless its SHA-256
matches `QUEUE_MODEL_SHA256`. Load it only through that check: joblib files can execute code.
