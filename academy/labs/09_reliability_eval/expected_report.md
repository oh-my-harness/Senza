# Senza Academy reliability report

Cases: 3 | k: 3

| Variant | Passed | Overall pass rate | Macro avg estimated Pass@k | Macro avg estimated Pass^k | Overall avg latency | Overall avg cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| bare | 4/9 | 0.444 | 0.790 | 0.123 | 438.89 ms | $0.001317 |
| guarded | 9/9 | 1.000 | 1.000 | 1.000 | 459.89 ms | $0.001593 |

Recommendation: **guarded** — highest macro-average estimated Pass^k, then overall pass rate, then lower average cost.

Limitations
- Recorded outcomes test the runner, not a live model.
- Each case's Pass@k and Pass^k use empirical p from only three repeated runs; macro averages weight cases equally.
- Audit, usage, and budget are inputs to evaluation; they are not a complete eval platform.
