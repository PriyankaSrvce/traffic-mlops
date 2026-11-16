# SUMO queue datasets (DVC-tracked)

These files are versioned with DVC (`*.csv.dvc` pointers in this folder; the CSVs themselves are git-ignored).
`dvc pull` downloads them once they have been pushed to the team's DVC remote.

| File | Rows | SHA-256 | Role |
|---|---:|---|---|
| `queue_training_labels_v1.csv` | 357,124 | `4e8213df71d3ed2df8bb2995ec195e1610f4398ad37f0e049a4399d9f93a5ffb` | Training data of production model v1 (18 SUMO runs, incident-quarantined) |
| `queue_training_labels_v2.csv` | 607,924 | `177130ea8b0622fd0575d9b2cb3a4c899a522a6e4fb3f02242defefb82fd93c4` | v1 data + 12 surge runs; training data of model v2 |
| `drift_surge_600.csv` | 55,556 | `b07bdcb20a88fe732fab159fabea28191440ff27dc5f95df475a6d5a53fd2104` | Simulated production batch: demand surge 600 veh/h, seeds 777 + 888 (never used for training) |
| `drift_surge_720.csv` | 63,688 | `370962df7f6ee06de2aaab425efa2c89eb81d3f039d0ac039dccb8c8996edb2f` | Simulated production batch: demand surge 720 veh/h, seeds 777 + 888 (never used for training) |
| `drift_sensor_fault_kmh.csv` | 112,176 | `3ad1b33b44933564976d61b70b418cad43d5039fee10329b6c3c5e46fa6364ef` | Synthetic sensor-fault batch: held-out test rows with speed x 3.6 (never used for training) |

The SHA-256 values are the dataset identities recorded by Metaflow (`dataset_sha256`) and in
`registry/model_versions.json`; DVC's own pointer files use MD5. Both identify the same bytes.
