# SLO / SLI

## SLI
- task intake success rate
- task completion rate
- median and p95 step latency
- event bus write success
- external connector availability

## Initial SLO
- intake success >= 99.5%
- p95 intake latency < 1s
- p95 step transition latency < 3s (excluding long-running external calls)
- audit event durability >= 99.99%

## Alerting
- connector error rate > 5% for 5 minutes
- blocked/failed task ratio > 20% over 15 minutes
- queue depth above threshold for 10 minutes
