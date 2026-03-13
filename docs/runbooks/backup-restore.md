# Runbook: Backup and Restore

## Backup
- PostgreSQL: daily full backup + WAL archival.
- retain 30 days for operational restore.

## Restore Drill
1. provision empty DB instance.
2. restore latest full backup and apply WAL.
3. run `alembic upgrade head`.
4. run smoke tests: health, ingress task create, trace retrieval.
