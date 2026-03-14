## Title
Docs PR Review Addressal Workflow

## Purpose
Inspect tracked PRs, detect actionable feedback, and dispatch accommodation tasks.

## Trigger
pr_review_addressal

## Required Inputs
- pr_ref

## Steps
1. Fetch fresh PR review state
- id: inspect_pr
- owned_by: product_analyst
- required_capabilities: pr_state_inspection,review_feedback_detection
- state_partition: pr_lifecycle
- on_success: dispatch_accommodation

2. Dispatch review feedback accommodation
- id: dispatch_accommodation
- owned_by: kite_runner
- required_capabilities: subworkflow_dispatch,task_routing,state_write
- state_partition: scheduler_run
- subworkflow_id: docs.review_feedback_accommodation
- subworkflow_version: 1
- on_success: completed

## Completion Criteria
Actionable feedback is either recorded as no-action or routed as accommodation task.

## Blocked Conditions
PR state cannot be fetched with required freshness.

## Failure Conditions
PR lifecycle context is missing or invalid.

## Rules
- one PR per workflow instance
- processed markers update only after actual PR update
