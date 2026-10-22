# Fixed-Time vs Adaptive Traffic Control

Results from two SUMO simulation seeds on the same synthetic network and route file. These are simulation results, not real-world Bengaluru performance measurements.

## Results by seed

| Seed | Control | Completed trips | Duration (s) | Waiting (s) | Time loss (s) | Route length (m) |
|---:|---|---:|---:|---:|---:|---:|
| 7 | Fixed | 900 | 89.39 | 15.22 | 27.74 | 822.00 |
| 7 | Adaptive | 900 | 82.99 | 8.92 | 21.32 | 821.95 |
| 21 | Fixed | 900 | 89.97 | 15.51 | 28.18 | 821.98 |
| 21 | Adaptive | 900 | 82.99 | 8.92 | 21.32 | 821.95 |

## Mean results across seeds

| Metric | Fixed-time mean | Adaptive mean | Reduction |
|---|---:|---:|---:|
| Average trip duration (s) | 89.68 | 82.99 | 7.46% |
| Average waiting time (s) | 15.36 | 8.92 | 41.96% |
| Average time loss (s) | 27.96 | 21.32 | 23.75% |
| Average route length (m) | 821.99 | 821.95 | 0.00% |

**Interpretation:** Lower duration, waiting time and time loss indicate improvement. Route length should remain similar because the compared simulations use the same predetermined routes. Only two seeds have been evaluated, so these results are preliminary.
