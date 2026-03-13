## Title
PR Promotion Workflow

## Purpose
Promote a PR only after checks and approvals.

## Trigger
User asks to promote a PR if checks are green.

## Required Inputs
- pr_number

## Steps
1. Evaluate PR readiness
- id: evaluate_readiness
- owned_by: docs_ops
- participants: qa,product_correctness
- required_capabilities: pr_read,review_analysis
- on_success: approval_gate
2. Approval gate
- id: approval_gate
- owned_by: product_correctness
- required_capabilities: product_review
- completion_type: approval_received
- on_success: promote_pr
- on_blocked: blocked
3. Promote PR
- id: promote_pr
- owned_by: docs_ops
- required_capabilities: pr_update
- policy_bindings: approval_required_before_promotion
- on_success: completed

## Completion Criteria
PR promoted via controlled path after approval.

## Blocked Conditions
Checks red or approval missing.

## Failure Conditions
Promotion action fails.

## Rules
- no direct merge
- approval required before promotion
