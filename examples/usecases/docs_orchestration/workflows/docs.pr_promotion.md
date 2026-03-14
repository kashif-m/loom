## Title
Docs PR Promotion Workflow

## Purpose
Evaluate promotion readiness and execute PR promotion lifecycle.

## Trigger
pr_promotion

## Required Inputs
- pr_ref
- promotion_context

## Steps
1. Evaluate promotion readiness
- id: evaluate_readiness
- owned_by: product_analyst
- required_capabilities: pr_state_inspection,promotion_readiness_evaluation
- state_partition: pr_lifecycle
- on_success: execute_promotion

2. Execute promotion lifecycle
- id: execute_promotion
- owned_by: product_analyst
- required_capabilities: promotion_execution
- state_partition: pr_lifecycle
- on_success: finalize_lifecycle

3. Finalize lifecycle and cleanup tracking
- id: finalize_lifecycle
- owned_by: product_analyst
- required_capabilities: cleanup_management,archival_management
- state_partition: cleanup_archive
- on_success: completed

## Completion Criteria
Promotion outcome is recorded and lifecycle state is preserved for terminal cleanup.

## Blocked Conditions
Promotion gates fail or stale PR state is detected.

## Failure Conditions
Promotion operation fails with non-recoverable state errors.

## Rules
- evaluate gates on fresh head state
- route resolvable blockers back into development workflow
