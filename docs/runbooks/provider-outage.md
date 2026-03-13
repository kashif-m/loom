# Runbook: Provider Outage

## Trigger
- OpenAI/Graphiti/LangSmith/OpenClaw connectivity failures exceed threshold.

## Immediate actions
1. Confirm provider status page and network connectivity.
2. Switch Loom to fallback mode via env toggles:
   - disable affected integration(s)
   - keep ingress available in degraded mode
3. Mark incidents and notify stakeholders.

## Recovery
1. Re-enable integration with canary traffic.
2. Verify task flow and tracing health.
3. Backfill failed or queued tasks if needed.
