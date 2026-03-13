## Title
PR Review Addressal Workflow

## Purpose
Address open review comments on an existing PR.

## Trigger
User asks to address comments on a PR.

## Required Inputs
- pr_number
- repository

## Steps
1. Fetch review comments
- id: fetch_review_comments
- owned_by: docs_ops
- required_capabilities: pr_read,review_analysis
- on_success: apply_updates
2. Apply requested updates
- id: apply_updates
- owned_by: technical_writer
- participants: development
- required_capabilities: repo_write,content_update
- on_success: rerun_validation
3. Re-run validation
- id: rerun_validation
- owned_by: qa
- participants: devex
- required_capabilities: validation,build_check,link_check
- on_success: update_pr
4. Update PR
- id: update_pr
- owned_by: docs_ops
- required_capabilities: pr_update
- on_success: completed

## Completion Criteria
PR comments addressed and PR updated.

## Blocked Conditions
PR not found or inaccessible.

## Failure Conditions
Validation failures after updates.

## Rules
- raise PR only
