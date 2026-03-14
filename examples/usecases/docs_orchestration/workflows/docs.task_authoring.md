## Title
Docs Task Authoring Workflow

## Purpose
Create or enhance documentation and produce a finalized package for execution.

## Trigger
task_authoring

## Required Inputs
- user_request
- task_object_ref

## Steps
1. Resolve request and context
- id: resolve_context
- owned_by: kite_runner
- required_capabilities: workflow_selection,context_resolution,fanout_management
- state_partition: task_workflow
- on_success: draft_package

2. Draft documentation package
- id: draft_package
- owned_by: technical_writer
- required_capabilities: package_writing,structural_editing,cross_reference_design
- on_success: run_audit

3. Run audit validation
- id: run_audit
- owned_by: testing
- required_capabilities: audit_execution,checklist_validation,explicit_failure_reporting
- on_success: finalize_package

4. Finalize package artifact
- id: finalize_package
- owned_by: kite_runner
- required_capabilities: package_aggregation,state_write,fanin_reporting
- state_partition: task_workflow
- on_success: completed

## Completion Criteria
Finalized package artifact is ready for development workflow.

## Blocked Conditions
Missing grounding sources or unresolved target mapping.

## Failure Conditions
Audit reports critical policy violations.

## Rules
- one task object per workflow instance
- preserve valuable existing content by default
- preserve diagrams by default
