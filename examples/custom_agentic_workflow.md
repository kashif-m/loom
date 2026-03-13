## Title
My Custom Local Workflow

## Purpose
Run a custom local agentic workflow with Loom.

## Trigger
User asks to run my custom workflow.

## Required Inputs
- topic

## Steps
1. Gather context
- id: gather_context
- owned_by: docs_ops
- required_capabilities: context_build
- on_success: draft_output

2. Draft output
- id: draft_output
- owned_by: technical_writer
- required_capabilities: markdown_write,content_update
- on_success: completed

## Completion Criteria
The output is drafted successfully.

## Blocked Conditions
Missing required input topic.

## Failure Conditions
Runtime adapter failures.

## Rules
- raise PR only
