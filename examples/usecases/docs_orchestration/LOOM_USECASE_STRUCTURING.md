# Structuring The Multi-Agent Documentation Orchestrator In Loom

This directory encodes the `docs.orchestration` use case as data:

- `bundle.yaml`:
  - organization settings
  - role (agent) definitions
  - capability definitions
  - policy definitions
  - prompt profiles
  - workflow registrations
- `workflows/*.md`:
  - markdown source-of-truth for workflow behavior

The runtime remains generic. No domain-specific orchestrator logic is hardcoded in the kernel.

Use:

```bash
loom ctl bundle apply --spec-file examples/usecases/docs_orchestration/bundle.yaml
```

Or in chat mode:

```text
/bundle apply examples/usecases/docs_orchestration/bundle.yaml
```
