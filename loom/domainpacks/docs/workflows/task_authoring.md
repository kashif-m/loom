## Title
Docs Task Authoring

## Purpose
Draft and update docs content and open/update a PR.

## Trigger
User asks to enhance docs or create docs.

## Required Inputs
- document_url
- repository

## Steps
1. Build context
- id: build_context
- owned_by: docs_ops
- participants: technical_writer,product_correctness
- required_capabilities: context_build,repo_read
- on_success: draft_content
2. Draft content
- id: draft_content
- owned_by: technical_writer
- participants: development
- required_capabilities: markdown_write,content_update
- on_success: run_validation
3. Run validation
- id: run_validation
- owned_by: qa
- participants: devex,diagramming
- required_capabilities: validation,link_check,style_check
- on_success: create_or_update_pr
4. Create or update PR
- id: create_or_update_pr
- owned_by: docs_ops
- required_capabilities: pr_create,pr_update
- on_success: completed

## Completion Criteria
PR created or updated with validated changes.

## Blocked Conditions
Missing repository access or required inputs.

## Failure Conditions
Validation failures or adapter failures.

## Rules
- no direct merge
- raise PR only
