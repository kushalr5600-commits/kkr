# Experiment results - split `validation`

1000 transactions, 102 true failures (ground truth = full stress simulation).
Ranking experiment: each policy ranks the split and the top budget fraction is simulated.

| budget | random | amount_only | anomaly_only | BLACKBOX |
|---|---|---|---|---|
| 0.5% | 0.005 | 0.010 | 0.020 | 0.020 |
| 1.0% | 0.010 | 0.020 | 0.059 | 0.039 |
| 2.0% | 0.019 | 0.020 | 0.147 | 0.078 |
| 5.0% | 0.049 | 0.020 | 0.324 | 0.137 |
| 10.0% | 0.102 | 0.039 | 0.529 | 0.196 |
| 100.0% | 1.000 | 1.000 | 1.000 | 1.000 |

Production rule (simulate iff score >= 0.60): simulates 11.4% of transactions, failure recall 0.216, precision 0.193.

Numbers are for the synthetic dataset only; weights and threshold are declared MVP parameters.
