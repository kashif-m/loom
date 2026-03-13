# Loom Threat Model

## Assets
- workflow definitions and compiled IR
- task payloads and memory data
- external provider credentials
- audit logs and traces

## Key Threats
- unauthorized admin operations
- prompt/tool injection into execution steps
- secret leakage via logs/traces
- unsafe command execution from adapters
- data exfiltration from memory backend

## Mitigations
- API key auth + admin role enforcement
- command allowlist policy guard
- secret redaction and startup validation
- scoped memory retrieval and invalidation
- audit logging and traceability hooks

## Residual Risks
- third-party provider outage and degraded behavior
- incorrect policy configuration by operators
- supply-chain vulnerabilities in dependencies
