# Runbook: Stuck Workflows

## Trigger
- task remains running without transitions beyond threshold
- async job in running state for too long

## Diagnosis
1. Inspect `/admin/tasks/{task_id}/trace`.
2. Inspect `/ingress/jobs/{job_id}` for error/status.
3. Check external connector health.

## Mitigation
1. retry task step from last known safe checkpoint.
2. move task to blocked with actionable summary.
3. create follow-up task for manual intervention if needed.
