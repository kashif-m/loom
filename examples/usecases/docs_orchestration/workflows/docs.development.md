## Title
Docs Development Workflow

## Purpose
Apply a finalized package in repository and create or update fork PR.

## Trigger
development

## Required Inputs
- package_ref
- repo_target_mapping

## Steps
1. Preflight and target verification
- id: preflight
- owned_by: developer
- required_capabilities: repo_target_validation,execution_preflight,technical_grounding
- on_success: execute_changes

2. Apply changes in isolated worktree
- id: execute_changes
- owned_by: developer
- required_capabilities: worktree_management,fork_branching,package_application
- on_success: fork_pr

3. Create or update fork PR
- id: fork_pr
- owned_by: developer
- required_capabilities: fork_pr_creation
- on_success: register_lifecycle

4. Register PR lifecycle tracking
- id: register_lifecycle
- owned_by: kite_runner
- required_capabilities: task_routing,state_write
- state_partition: scheduler_run
- on_success: completed

## Completion Criteria
Fork PR is created or updated and tracked.

## Blocked Conditions
Preflight fails or repository target is unresolved.

## Failure Conditions
Execution cannot be safely applied in current repository context.

## Rules
- fork-first discipline is mandatory
- no main PR creation during development workflow
