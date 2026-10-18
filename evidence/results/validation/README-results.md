# Experiment results - split `validation`

1000 transactions, 102 true failures (ground truth = full stress simulation).
Ranking experiment: each policy ranks the split and the top budget fraction is simulated.

| budget | random | amount_only | anomaly_only | BLACKBOX |
|---|---|---|---|---|
| 0.5% | 0.005 | 0.010 | 0.049 | 0.029 |
| 1.0% | 0.010 | 0.020 | 0.098 | 0.059 |
| 2.0% | 0.019 | 0.020 | 0.176 | 0.108 |
| 5.0% | 0.049 | 0.020 | 0.422 | 0.167 |
| 10.0% | 0.102 | 0.039 | 0.696 | 0.245 |
| 100.0% | 1.000 | 1.000 | 1.000 | 1.000 |

Production rule (simulate iff score >= 0.60): simulates 16.5% of transactions, failure recall 0.314, precision 0.194.

Numbers are for the synthetic dataset only; weights and threshold are declared MVP parameters.
