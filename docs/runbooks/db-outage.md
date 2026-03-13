# Runbook: Database Outage

## Trigger
- DB connection failures, migration failures, or high error rate.

## Immediate actions
1. Pause async workers.
2. Switch ingress to maintenance mode if writes are unsafe.
3. Validate DB endpoint, credentials, and connectivity.

## Recovery
1. Restore database service and verify migrations.
2. Resume workers.
3. Replay queued tasks where possible.
