# Full-dataset run report

This file records the final run that produced `output.csv`.

## Run

- Mode: evaluation
- Output file: output.csv
- Requests written: 250
- Unique users: 250
- Started (UTC): 2026-09-12T20:06:35Z
- Finished (UTC): 2026-09-12T20:06:43Z
- Wall time (seconds): 7.97
- Throughput (requests/second): 31.371
- Forecast horizon (days): 90
- Decision engine: deterministic financial graph with local evidence extractors

## Ledger and evidence coverage

- Financial profiles: 275
- Financial events: 25342
- Payment-option rows: 790
- Exchange-rate rows: 134
- Images resolved: 11
- Messages parsed: 198
- Vision cache files: 16
- Message cache files: 192
- Non-empty explanations: 250

## Decision mix

### Affordability status

| Status | Count | Share |
|---|---:|---:|
| `affordable_later` | 53 | 21.2% |
| `affordable_now` | 70 | 28.0% |
| `affordable_with_plan` | 65 | 26.0% |
| `not_affordable` | 62 | 24.8% |

### Recommended payment method

| Method | Count | Share |
|---|---:|---:|
| `full_payment` | 75 | 30.0% |
| `installments` | 56 | 22.4% |
| `not_recommended` | 70 | 28.0% |
| `partial_payment` | 4 | 1.6% |
| `wait` | 45 | 18.0% |

## Provider usage

- Provider: none (local rules + image catalog)
- Text model: `none`
- Vision model: `none`

| Model | Calls | Input tokens | Output tokens | Total tokens | Estimated cost (USD) |
|---|---:|---:|---:|---:|---:|
| `local-rules+catalog` | 0 | 0 | 0 | 0 | 0.000000 |
| **All** | **0** | **0** | **0** | **0** | **0.000000** |

- Requests processed: 250
- Average input tokens per request: 0.00
- Average output tokens per request: 0.00
- Average total tokens per request: 0.00
- Estimated average cost per request (USD): 0.000000
- Estimated total cost (USD): 0.000000

## Notes

- API keys, credentials, and environment secrets are not included.
- Every plan is checked against the 90-day cash forecast and the minimum-balance constraint before a row is written.
