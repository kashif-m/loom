## Title
Docs Development Workflow

## Purpose
Implement requested docs-related development updates.

## Trigger
User asks to develop or implement docs changes.

## Required Inputs
- repository
- branch

## Steps
1. Build implementation context
- id: build_impl_context
- owned_by: development
- participants: docs_ops
- required_capabilities: context_build,repo_read
- on_success: implement_changes
2. Implement changes
- id: implement_changes
- owned_by: development
- participants: technical_writer
- required_capabilities: repo_write,content_update
- on_success: run_checks
3. Run checks
- id: run_checks
- owned_by: devex
- participants: qa
- required_capabilities: build_check,style_check,link_check
- on_success: open_pr
4. Open PR
- id: open_pr
- owned_by: docs_ops
- required_capabilities: pr_create
- on_success: completed

## Completion Criteria
A PR is opened with checks passing.

## Blocked Conditions
Missing branch or repository details.

## Failure Conditions
Build or validation failures.

## Rules
- no direct merge
