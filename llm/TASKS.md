# TASKS.md

# Loom Implementation Backlog

**System name:** Loom
**Primary goal:** Implement a generic workflow-first multi-agent orchestration kernel in Python
**Primary first-party domain pack:** Docs Pack
**Initial ingress surface:** `/ff ...` on top of OpenClaw
**Deployment target:** Local-first, container-friendly, Nix-friendly

---

# 1. How to Use This Backlog

This document is written as an execution plan for a coding agent or implementation team.

Each task includes:

* intent,
* scope,
* detailed work items,
* expected deliverables,
* acceptance criteria,
* dependencies,
* implementation notes.

The backlog is intentionally verbose so that implementation can proceed with minimal ambiguity.

This backlog assumes the following documents already define the product:

* `PRD.md`
* `ARCHITECTURE.md`

This file focuses on execution.

---

# 2. Delivery Rules

## 2.1 Kernel-first

Do not start by hardcoding Docs Pack behaviors into the kernel.
The kernel must remain generic.

## 2.2 Registry-driven

Do not implement roles, workflows, policies, or capabilities as bespoke hardcoded classes unless absolutely necessary.

## 2.3 Markdown workflows are source of truth

Do not make compiled YAML the primary authoring layer.

## 2.4 No step without ownership

Every compiled step must have explicit ownership and completion semantics.

## 2.5 No task without workflow

Every task entering Loom must resolve to a workflow before execution.

## 2.6 Keep OpenClaw thin

OpenClaw is ingress, not the kernel.

## 2.7 Keep Docs Pack separable

All docs-specific behavior must live in Docs Pack or docs adapters.

## 2.8 Preserve observability

Every meaningful state transition must emit traceable events.

---

# 3. Target Repository Shape

Create a repository with a structure roughly like this:

```text
loom/
├── loom/
│   ├── app/
│   ├── ingress/
│   ├── triage/
│   ├── kernel/
│   ├── compiler/
│   ├── registries/
│   ├── memory/
│   ├── execution/
│   ├── observability/
│   ├── scheduling/
│   ├── adapters/
│   ├── domainpacks/
│   │   └── docs/
│   └── persistence/
├── tests/
├── examples/
├── scripts/
├── Dockerfile
├── flake.nix
├── pyproject.toml
├── README.md
├── PRD.md
├── ARCHITECTURE.md
└── TASKS.md
```

---

# 4. Phase Overview

Implementation should proceed in the following phases:

1. Project foundation
2. Core schemas and persistence
3. Registries
4. Workflow markdown compiler
5. Task intake and triage
6. Kernel runtime
7. Memory layer
8. Observability and topology
9. Scheduling
10. OpenClaw ingress
11. Docs Pack
12. Verification and PR operations
13. Integration and end-to-end tests
14. Packaging and developer environment
15. Hardening and cleanup

The coding agent should complete each phase with passing tests before progressing aggressively into the next one.

---

# 5. Phase 1 — Project Foundation

## [x] TASK-001: Initialize Python project

### Objective

Create the base Python application and package structure.

### Work

* Create the `loom/` Python package.
* Set up `pyproject.toml` using a modern build system.
* Add runtime dependencies and dev dependencies.
* Configure formatting, linting, and static checks.
* Add a minimal `README.md` with project purpose and run instructions.
* Add package init files for all major modules.

### Deliverables

* `pyproject.toml`
* initial package structure
* formatter/linter/type-check config
* project bootstrap scripts

### Acceptance Criteria

* `pip install -e .` works
* project imports cleanly
* linters/type-checkers run without fatal config errors

### Dependencies

None

---

## [x] TASK-002: Add application entrypoint

### Objective

Create a basic application bootstrap layer.

### Work

* Add `loom/app/main.py`
* Add config loading module
* Add dependency wiring module
* Add startup/shutdown hooks
* Add health endpoint or health command

### Deliverables

* runnable app bootstrap
* config loader
* app wiring skeleton

### Acceptance Criteria

* app starts locally
* config loads from environment
* health endpoint or equivalent status call returns successfully

### Dependencies

TASK-001

---

# 6. Phase 2 — Core Schemas and Persistence

## [x] TASK-003: Implement canonical core schemas

### Objective

Create canonical Pydantic models for all major kernel entities.

### Work

Implement models for:

* Task
* WorkflowDefinitionMetadata
* WorkflowMarkdownDocument
* CompiledWorkflowIR
* CompiledWorkflowStep
* RoleDefinition
* RuntimeParticipant
* CapabilityDefinition
* PromptProfile
* PolicyDefinition
* DomainPackManifest
* ScheduleDefinition
* TaskEvent
* MemoryScopeReference

### Deliverables

* schema modules under `loom/`
* tests validating schema parsing and validation

### Acceptance Criteria

* all schemas serialize/deserialize cleanly
* invalid shapes fail validation predictably

### Dependencies

TASK-001

---

## [x] TASK-004: Implement persistence layer

### Objective

Create a persistence strategy for tasks, workflows, registries, schedules, and event logs.

### Work

* Choose a persistence backend for v1 (SQLite preferred for simplicity).
* Create DB models or repository abstractions.
* Add migration support.
* Implement CRUD repositories for:

  * tasks
  * workflows
  * compiled workflow IR
  * roles
  * capabilities
  * prompt profiles
  * policies
  * domain packs
  * schedules
  * runtime participants
  * event logs

### Deliverables

* DB schema
* migration scripts
* repository interfaces and implementations

### Acceptance Criteria

* data survives restarts
* CRUD works for all first-class entities
* migrations can create fresh DB cleanly

### Dependencies

TASK-003

---

# 7. Phase 3 — Registries

## [x] TASK-005: Implement workflow registry

### Objective

Allow registration, retrieval, update, activation, deprecation, and archival of workflow definitions.

### Work

* Implement workflow registry service.
* Support markdown workflow storage.
* Support compiled IR storage.
* Support active version lookup by workflow ID.
* Support draft → active transition only after validation.
* Support deprecating old versions.

### Deliverables

* workflow registry service
* tests covering versioning and active lookup

### Acceptance Criteria

* can create draft workflow
* can activate valid workflow version
* can deprecate old versions
* new tasks always resolve to active version

### Dependencies

TASK-004

---

## [x] TASK-006: Implement role registry

### Objective

Define and manage role definitions independent of hardcoded Python classes.

### Work

* Implement role CRUD.
* Store role metadata, capability set, policy bindings, memory visibility, and domain-pack ownership.
* Add validation for duplicate role IDs.
* Add status management: draft, active, retired, archived.

### Acceptance Criteria

* roles can be created, updated, retired, and retrieved
* role definitions are independent of bespoke runtime classes

### Dependencies

TASK-004

---

## [x] TASK-007: Implement capability registry

### Objective

Create a registry for capabilities used by steps and roles.

### Work

* Implement CRUD for capabilities.
* Add bindings to connectors/adapters.
* Add optional validation requirements.

### Acceptance Criteria

* workflows and roles can reference capabilities by ID
* invalid capability references are caught during validation

### Dependencies

TASK-004

---

## [x] TASK-008: Implement policy registry

### Objective

Store and resolve explicit policy definitions.

### Work

* Implement policy CRUD.
* Support workflow-scoped, role-scoped, and global policies.
* Add enforcement modes.
* Provide policy resolution service.

### Acceptance Criteria

* policies can be attached to workflows and roles
* policy engine can resolve effective policy set for a task or step

### Dependencies

TASK-004

---

## [x] TASK-009: Implement prompt profile registry

### Objective

Store prompt profiles separately from role and workflow definitions.

### Work

* Implement prompt profile CRUD.
* Add versioning support.
* Add domain pack ownership.
* Allow role and workflow step bindings.

### Acceptance Criteria

* profiles resolve correctly by ID/version
* changing a prompt profile does not require code changes

### Dependencies

TASK-004

---

## [x] TASK-010: Implement domain pack registry

### Objective

Allow domain packs to be loaded and managed as first-class extensions.

### Work

* Define domain pack manifest schema.
* Implement load, validate, activate, deactivate.
* Domain pack should contribute:

  * workflows
  * roles
  * capabilities
  * policies
  * prompt profiles
  * connectors/adapters
  * validation rules

### Acceptance Criteria

* Docs Pack can be loaded through this registry later
* kernel remains generic

### Dependencies

TASK-004

---

## [x] TASK-011: Implement schedule registry

### Objective

Persist and manage schedules.

### Work

* Implement CRUD for schedules.
* Store cron expression, target workflow or maintenance action, payload, enable/disable flags.

### Acceptance Criteria

* schedules can be created, updated, disabled, and deleted
* schedule definitions survive restart

### Dependencies

TASK-004

---

# 8. Phase 4 — Workflow Markdown Compiler

## [x] TASK-012: Implement workflow markdown parser

### Objective

Parse structured markdown workflows into normalized sections.

### Work

* Read workflow markdown files.
* Parse section headings.
* Extract required sections:

  * Title
  * Purpose
  * Trigger
  * Required Inputs
  * Steps
  * Completion Criteria
  * Blocked Conditions
  * Failure Conditions
  * Rules
* Normalize ordered steps.
* Preserve source location info for error reporting if practical.

### Acceptance Criteria

* valid markdown document becomes normalized parsed object
* missing required sections fail clearly

### Dependencies

TASK-003

---

## [x] TASK-013: Implement LLM-assisted workflow compiler

### Objective

Convert normalized workflow markdown into compiled IR.

### Work

* Build compiler prompt that translates normalized markdown into low-level YAML or internal structured IR.
* Keep markdown as source of truth.
* Emit deterministic, structured output as much as possible.
* Ensure compiler extracts:

  * workflow metadata
  * selection hints
  * ordered step IR
  * ownership hints
  * capability hints
  * transitions
  * completion semantics
  * terminal states
  * policy hints
  * memory hints

### Acceptance Criteria

* valid workflow markdown compiles into structured IR
* compiler output is stable enough for validation and storage

### Dependencies

TASK-012

---

## [x] TASK-014: Implement workflow IR validator

### Objective

Ensure compiled workflow IR is executable and safe.

### Work

Validate that:

* workflow ID exists
* version is valid
* all step IDs are unique
* every step has `owned_by`
* every referenced role exists
* every referenced capability exists
* transitions point to valid steps or terminal states
* terminal states exist
* completion rules are resolvable
* policy bindings reference existing policies
* memory bindings are well-formed

### Acceptance Criteria

* invalid compiled workflow cannot be activated
* validator returns actionable error messages

### Dependencies

* TASK-005
* TASK-006
* TASK-007
* TASK-008
* TASK-013

---

## [x] TASK-015: Implement compiler service and publication flow

### Objective

Provide end-to-end workflow publication from markdown to active compiled version.

### Work

* Add service to:

  * load markdown
  * parse
  * compile
  * validate
  * persist
  * activate or reject
* Support draft activation flow.
* Support replacement of old active version.
* Trigger memory invalidation policy for deprecated versions.

### Acceptance Criteria

* a markdown workflow can become active through one command or API call
* old versions remain audit-visible

### Dependencies

TASK-012
TASK-013
TASK-014

---

# 9. Phase 5 — Task Intake and Triage

## [x] TASK-016: Implement request intake service

### Objective

Accept natural-language requests and create task records.

### Work

* Implement intake endpoint/service.
* Create task record in `created` state.
* Store raw request and metadata.
* Forward request to triage.

### Acceptance Criteria

* natural-language request results in a persisted task

### Dependencies

TASK-004

---

## [x] TASK-017: Implement classifier

### Objective

Classify requests into workflow intent groups.

### Work

* Build classification component.
* Support confidence scoring.
* Map classifier output to active workflows.
* Support “unsupported” and “needs minimal clarification” outcomes.

### Acceptance Criteria

* supported docs requests route correctly to one of the four initial workflows
* unsupported requests return explicit response

### Dependencies

TASK-005
TASK-016

---

## [x] TASK-018: Implement entity extractor

### Objective

Extract relevant entities from natural-language requests.

### Work

Extract items such as:

* PR number
* repository name
* document URL
* branch name
* optional environment hints

### Acceptance Criteria

* extraction works on primary example requests
* extracted entities are attached to task state

### Dependencies

TASK-016

---

## [x] TASK-019: Implement workflow selector

### Objective

Resolve the final workflow version for a task.

### Work

* Combine classifier output, entities, workflow metadata, and active registry state.
* Select workflow ID and active version.
* Update task state to `workflow_selected`.

### Acceptance Criteria

* workflow selection is explicit and persisted
* tasks do not enter execution without workflow selection

### Dependencies

TASK-017
TASK-018

---

# 10. Phase 6 — Kernel Runtime

## [x] TASK-020: Implement task state machine

### Objective

Create the canonical task lifecycle and transition rules.

### Work

Implement allowed transitions for:

* created
* triaging
  n- workflow_selected
* running
* awaiting_input
* blocked
* failed
* completed
* archived

Also implement invalid transition rejection.

### Acceptance Criteria

* task state transitions are explicit and tested

### Dependencies

TASK-003
TASK-004

---

## [x] TASK-021: Implement participant resolver

### Objective

Resolve role ownership into concrete runtime participants.

### Work

* Resolve step `owned_by` roles into runtime participant instances.
* Resolve `participants` collaborators.
* Enforce capability satisfaction.
* Enforce spawn constraints.
* Support reusing existing participants when allowed.
* Support creating new runtime participants when needed.

### Acceptance Criteria

* step ownership resolves into valid participant set
* capability mismatch fails clearly

### Dependencies

TASK-006
TASK-007
TASK-020

---

## [x] TASK-022: Implement execution planner

### Objective

Plan which step runs next and what context must be assembled.

### Work

* Load compiled workflow IR.
* Enter first step.
* Evaluate transitions after each step.
* Support terminal transitions.
* Support blocked and failure transitions.

### Acceptance Criteria

* workflow step order follows compiled IR reliably

### Dependencies

TASK-015
TASK-020

---

## [x] TASK-023: Implement step runner

### Objective

Execute a single step given compiled IR and resolved participants.

### Work

* Read step definition.
* Assemble inputs.
* Bind owners and collaborators.
* Invoke participant execution.
* Capture outputs.
* Evaluate completion.
* Emit events.

### Acceptance Criteria

* a simple step can run end-to-end and write outputs to task state

### Dependencies

TASK-021
TASK-022

---

## [x] TASK-024: Implement collaborative step runner

### Objective

Support multi-participant step execution.

### Work

Support spawn strategies:

* single_owner
* primary_with_support
* parallel_research
* consensus_required
* any_one_can_complete

Implement merge behavior such as:

* owner_synthesizes
* first_valid_output
* consensus_summary
* explicit_human_choice

### Acceptance Criteria

* one workflow step can use multiple participants correctly
* outputs are merged according to merge policy

### Dependencies

TASK-023

---

## [x] TASK-025: Implement completion evaluator

### Objective

Determine when a step is complete.

### Work

Support completion types:

* all_outputs_present
* predicate
* approval_received
* all_participants_complete
* any_participant_complete

### Acceptance Criteria

* completion logic works across multiple step shapes

### Dependencies

TASK-023
TASK-024

---

## [x] TASK-026: Implement transition engine

### Objective

Transition task execution based on step outcomes.

### Work

* Apply `on_success`, `on_blocked`, `on_failure`, `on_retry`.
* Move to next step or terminal state.
* Update task state and event log.

### Acceptance Criteria

* step outcomes transition correctly and deterministically

### Dependencies

TASK-025

---

## [x] TASK-027: Implement policy engine

### Objective

Enforce policies during runtime.

### Work

* Resolve global + workflow + role + step policies.
* Enforce examples such as:

  * no direct merge
  * raise PR only
  * approval required before promotion
  * memory visibility restriction
  * write restriction for certain steps

### Acceptance Criteria

* policy violations block execution predictably

### Dependencies

TASK-008
TASK-026

---

# 11. Phase 7 — Memory Layer

## [x] TASK-028: Implement memory service abstraction

### Objective

Create a generic memory service interface.

### Work

Support:

* working memory
* episodic memory
* semantic memory
* consolidation
* invalidation
* scoped retrieval

### Acceptance Criteria

* kernel can read and write memory through one abstraction

### Dependencies

TASK-003

---

## [x] TASK-029: Implement Graphiti adapter

### Objective

Connect Loom memory service to Graphiti.

### Work

* Implement create/read/update/delete flows for episodic entries where appropriate.
* Support scoped retrieval by workflow version, domain pack, role, and entity.
* Support writeback after task completion.

### Acceptance Criteria

* Graphiti-backed memory read/write works for pilot scenarios

### Dependencies

TASK-028

---

## [x] TASK-030: Implement memory scoping rules

### Objective

Ensure memory retrieval is safe and relevant.

### Work

* Implement scope resolution by:

  * workflow ID
  * workflow version
  * role
  * domain pack
  * linked entities
  * task lineage
* Add active-workflow-first retrieval rule.

### Acceptance Criteria

* stale/deprecated workflow memory is not surfaced by default

### Dependencies

TASK-028
TASK-029

---

## [x] TASK-031: Implement consolidation / sleep

### Objective

Condense episodic memory into semantic memory.

### Work

* Build consolidation job.
* Summarize useful recurring patterns.
* Persist higher-order memory artifacts.
* Attach provenance.

### Acceptance Criteria

* completed tasks result in useful consolidated memory over time

### Dependencies

TASK-029

---

## [x] TASK-032: Implement forgetting / invalidation

### Objective

Support memory invalidation when workflows evolve.

### Work

* Implement soft forgetting by excluding deprecated workflow scopes.
* Implement explicit hard invalidation path.
* Record invalidation events.

### Acceptance Criteria

* deprecated workflow memory can be hidden from active retrieval
* explicit invalidation path is supported

### Dependencies

TASK-031
TASK-015

---

# 12. Phase 8 — Observability and Topology

## [x] TASK-033: Implement event bus and audit log

### Objective

Record all important runtime events.

### Work

Emit events for:

* task created
* triage started/completed
* workflow selected
* step entered
* participant resolved
* memory read/write
* step completed
* step blocked
* step failed
* schedule triggered
* task completed

### Acceptance Criteria

* events are persisted and queryable

### Dependencies

TASK-004
TASK-023

---

## [x] TASK-034: Implement trace service

### Objective

Expose structured run traces.

### Work

* Build trace aggregation layer.
* Connect to LangSmith where appropriate.
* Map task/step lifecycle to traceable spans.

### Acceptance Criteria

* a complete workflow run can be inspected step by step

### Dependencies

TASK-033

---

## [x] TASK-035: Implement topology generator

### Objective

Render real-time system topology.

### Work

* Generate Mermaid representation from:

  * active roles
  * active runtime participants
  * current task bindings
  * workflow ownership structure
* Expose topology endpoint or file generation.

### Acceptance Criteria

* Mermaid topology reflects current organization and active assignments

### Dependencies

TASK-006
TASK-021
TASK-033

---

# 13. Phase 9 — Scheduling

## [x] TASK-036: Implement scheduler service

### Objective

Run time-based actions and workflows.

### Work

* Integrate APScheduler.
* Load schedules from registry.
* Support enable/disable/update/delete.
* Trigger workflow or maintenance action with payload.

### Acceptance Criteria

* schedules execute at expected times
* schedule runs are logged and traceable

### Dependencies

TASK-011

---

## [x] TASK-037: Implement initial maintenance schedules

### Objective

Ship a few useful built-in schedules.

### Work

Implement schedules for:

* nightly memory consolidation
* stale PR scan
* docs freshness scan
* topology regeneration

### Acceptance Criteria

* at least one maintenance schedule works end-to-end in local/dev mode

### Dependencies

TASK-036
TASK-031
TASK-035

---

# 14. Phase 10 — OpenClaw Ingress

## [x] TASK-038: Implement OpenClaw ingress adapter

### Objective

Receive `/ff ...` requests via OpenClaw and forward them into Loom.

### Work

* Implement adapter or plugin integration.
* Accept natural-language requests.
* Forward to intake service.
* Stream result updates back if possible.

### Acceptance Criteria

* `/ff enhance these docs <url>` reaches Loom and creates a task

### Dependencies

TASK-016

---

## [x] TASK-039: Implement admin ingress surface

### Objective

Expose controlled admin operations for workflows, roles, schedules, and packs.

### Work

Support admin operations for:

* workflow publish
* workflow activate/deprecate
* role create/update/retire
* domain pack load
* schedule create/update/delete
* memory invalidation trigger

### Acceptance Criteria

* core admin flows can be executed from ingress or API

### Dependencies

TASK-005
TASK-006
TASK-010
TASK-011
TASK-032
TASK-038

---

# 15. Phase 11 — Docs Pack

## [x] TASK-040: Create Docs Pack manifest

### Objective

Define Docs Pack as the first domain pack.

### Work

Create manifest including:

* pack metadata
* workflows included
* roles included
* capabilities included
* prompt profiles included
* policies included
* connectors/adapters included
* validations included

### Acceptance Criteria

* Docs Pack loads through domain pack registry

### Dependencies

TASK-010

---

## [x] TASK-041: Add Docs Pack roles and capabilities

### Objective

Register initial Docs Pack role and capability definitions.

### Work

Add roles such as:

* docs_ops
* development
* technical_writer
* product_correctness
* diagramming
* devex
* qa
* infra
* marketing

Add capabilities such as:

* repo_read
* repo_write
* pr_read
* pr_update
* pr_create
* context_build
* review_analysis
* content_update
* markdown_write
* diagram_generation
* validation
* build_check
* link_check
* style_check
* developer_review
* product_review
* infra_review
* market_research

### Acceptance Criteria

* roles and capabilities resolve correctly through registries

### Dependencies

TASK-006
TASK-007
TASK-040

---

## [x] TASK-042: Add initial Docs Pack workflow markdown files

### Objective

Define the first four workflows in markdown.

### Work

Create workflow markdown files for:

1. Task Authoring
2. Development
3. PR Review Addressal
4. PR Promotion

Use the structured markdown template.

### Acceptance Criteria

* all four workflows parse, compile, and validate

### Dependencies

TASK-015
TASK-040

---

## [x] TASK-043: Add Docs Pack prompt profiles

### Objective

Provide prompt profiles for initial Docs Pack behavior.

### Work

Define profiles for:

* docs writer
* docs ops
* PM-style correctness review
* devex review
* diagram generation
* QA review
* marketing review
* infra review
* development/repo context synthesis

### Acceptance Criteria

* prompt profiles resolve cleanly during step execution

### Dependencies

TASK-009
TASK-040

---

## [x] TASK-044: Implement Docs Pack context assembly

### Objective

Assemble repository, documentation, PR, and memory context for docs workflows.

### Work

* Implement OpenCode integration for repository context.
* Assemble context packs from:

  * repository source
  * existing docs
  * PR metadata
  * memory slices
* Cache within task scope when appropriate.

### Acceptance Criteria

* docs workflows can gather enough context to draft/update content

### Dependencies

TASK-041
TASK-042
TASK-029

---

# 16. Phase 12 — Validation and PR Operations

## [x] TASK-045: Implement git adapter

### Objective

Support local branch and commit operations.

### Work

Implement actions for:

* branch creation
* checkout
* add/remove/update files
* commit changes
* push branch

### Acceptance Criteria

* local branch-based update flow works from Python

### Dependencies

TASK-001

---

## [x] TASK-046: Implement gh adapter

### Objective

Support PR create/read/update/promote actions.

### Work

Implement actions for:

* PR create
* PR read
* comment retrieval
* review comment retrieval
* PR update
* PR merge/promotion path

### Acceptance Criteria

* Docs Pack workflows can interact with GitHub through gh

### Dependencies

TASK-045

---

## [x] TASK-047: Implement PlantUML adapter

### Objective

Support Docs Pack diagram generation and verification.

### Work

* Generate and render `.puml`.
* Capture compile/render failures.
* Return structured results.

### Acceptance Criteria

* PlantUML render path works in local dev and containerized environment

### Dependencies

TASK-001

---

## [x] TASK-048: Implement verification pipeline

### Objective

Support Docs Pack verification before PR completion/promotion.

### Work

Implement validation actions for:

* markdown/MDX build
* PlantUML render
* link checking
* style/prose checking

### Acceptance Criteria

* verification returns structured pass/fail output
* failure details are attached to task state

### Dependencies

TASK-047
TASK-045
TASK-046

---

## [x] TASK-049: Bind validation and PR operations into Docs Pack workflows

### Objective

Make docs workflows produce real PR-based outcomes.

### Work

* Bind validation steps into compiled workflows.
* Bind PR creation/update steps.
* Enforce no-direct-merge policy by default.

### Acceptance Criteria

* task authoring workflow can end in PR creation/update
* PR promotion workflow can enforce checks before promotion path

### Dependencies

TASK-042
TASK-048

---

# 17. Phase 13 — Integration and End-to-End Testing

## [x] TASK-050: Unit tests for all core modules

### Objective

Create robust test coverage for schemas, registries, compiler, state machine, policy engine, memory service, and adapters.

### Acceptance Criteria

* all major modules have meaningful test coverage

### Dependencies

All previous relevant tasks

---

## [x] TASK-051: Integration tests for workflow compilation and execution

### Objective

Test markdown workflow → compiled IR → task execution.

### Work

* add fixtures for workflow markdown
* add fixture domain pack
* run a full task through kernel with mocked adapters

### Acceptance Criteria

* at least one docs workflow completes end-to-end in integration tests

### Dependencies

TASK-015
TASK-026
TASK-049

---

## [x] TASK-052: End-to-end test via ingress

### Objective

Simulate user request from `/ff ...` to final result.

### Work

* run full path from ingress to PR or simulated PR result
* verify traces and topology update

### Acceptance Criteria

* primary happy path works end-to-end

### Dependencies

TASK-038
TASK-049

---

# 18. Phase 14 — Packaging and Developer Environment

## [x] TASK-053: Add Dockerfile

### Objective

Containerize Loom for easy local and deployment usage.

### Requirements

The Dockerfile must support:

* Python runtime
* system dependencies for git and gh
* Node or equivalent dependency support for docs build if needed
* PlantUML runtime support
* sane caching and layer ordering
* non-root execution if practical
* environment-variable-based configuration

### Suggested shape

* Use a slim Python base image.
* Install system packages:

  * git
  * gh
  * curl
  * Java runtime for PlantUML if needed
  * Node.js if required for MDX build
* Copy `pyproject.toml` and lock files first.
* Install Python dependencies.
* Copy source tree.
* Set working directory.
* Expose app port if API is used.
* Define a default run command.

### Acceptance Criteria

* `docker build` succeeds
* container starts Loom successfully
* docs-related adapters can run inside the container

### Dependencies

TASK-001
TASK-047
TASK-048

---

## [x] TASK-054: Add flake.nix

### Objective

Provide a reproducible Nix development environment.

### Requirements

The flake should install everything needed for local development, including:

* Python
* pip/uv/poetry as chosen package manager support
* git
* gh
* Java runtime for PlantUML
* Node.js for docs build if required
* shell helpers for running app, tests, linting, formatting
* environment variable wiring placeholders

### Suggested outputs

* `devShells.default`
* optional package output if useful later

### Suggested contents

* python interpreter and packaging helpers
* git
* gh
* nodejs
* jre
* graphviz if needed by PlantUML paths used
* common dev utilities

### Acceptance Criteria

* `nix develop` drops user into a working Loom dev shell
* all core commands run from the Nix shell

### Dependencies

TASK-001
TASK-047
TASK-048

---

# 19. Phase 15 — Hardening and Cleanup

## [x] TASK-055: Enforce config validation

### Objective

Fail fast on invalid runtime configuration.

### Work

* validate all required env vars and config fields
* add startup checks for connector availability

### Acceptance Criteria

* app fails fast with clear messages on invalid config

### Dependencies

TASK-002

---

## [x] TASK-056: Harden unsupported / blocked flows

### Objective

Ensure user-facing outcomes are clean and explicit.

### Work

* improve unsupported responses
* improve blocked responses
* improve failure summaries
* include actionable detail without leaking internals unnecessarily

### Acceptance Criteria

* user-facing responses are predictable and helpful

### Dependencies

TASK-017
TASK-026

---

## [x] TASK-057: Clean API boundaries

### Objective

Ensure kernel remains generic and domain packs remain isolated.

### Work

* review imports and dependencies
* remove docs-specific assumptions from kernel modules
* enforce adapter boundaries

### Acceptance Criteria

* kernel modules do not import Docs Pack internals except through registry/pack interfaces

### Dependencies

All major implementation tasks

---

## [x] TASK-058: Final developer documentation

### Objective

Make Loom understandable and runnable for future contributors.

### Work

* update README
* add local setup guide
* add architecture references
* add workflow authoring guide
* add domain pack authoring guide

### Acceptance Criteria

* new developer can bootstrap Loom with README + flake + Dockerfile

### Dependencies

TASK-053
TASK-054
TASK-057

---

# 20. Suggested Build Order Summary

If the coding agent needs a condensed order of execution, use this:

1. TASK-001 → TASK-004
2. TASK-005 → TASK-011
3. TASK-012 → TASK-015
4. TASK-016 → TASK-019
5. TASK-020 → TASK-027
6. TASK-028 → TASK-032
7. TASK-033 → TASK-037
8. TASK-038 → TASK-039
9. TASK-040 → TASK-044
10. TASK-045 → TASK-049
11. TASK-050 → TASK-052
12. TASK-053 → TASK-054
13. TASK-055 → TASK-058

---

# 21. Minimum Viable v1 Cut

If implementation must be staged, the smallest useful v1 is:

* workflow markdown parser
* workflow compiler + validator
* workflow registry
* role registry
* capability registry
* task intake + triage
* task state machine
* participant resolver
* step runner
* policy engine
* Graphiti-backed memory read/write
* OpenClaw ingress
* Docs Pack with only:

  * Task Authoring Workflow
  * PR Review Addressal Workflow
* git + gh integration
* validation pipeline
* Dockerfile
* flake.nix

Everything else can layer on top.

---

# 22. Final Instruction to Coding Agent

Do not implement Loom as a docs-only app.
Do not represent roles as hardcoded bespoke agent files by default.
Do not represent workflows as hardcoded Python graphs by default.
Do not bypass the markdown → compiled IR → validated execution flow.
Do not let a task execute without a selected workflow.
Do not let deprecated workflow memory leak into active retrieval by default.
Do not let the Docs Pack contaminate kernel design.

Build the kernel first.
Then build Docs Pack on top.
Then prove the architecture through the docs use case.

---

# 23. Phase 16 — External Platform Integrations (Real, Not Stubs)

## [x] TASK-059: Replace Graphiti stub with real Graphiti integration

### Objective

Use a real Graphiti backend for episodic/semantic memory operations.

### Work

* Add Graphiti client dependency and typed adapter implementation.
* Implement authenticated connect/read/write/update/delete flows.
* Add retry + timeout + circuit-breaker behavior.
* Add tenant/workspace namespacing support.
* Add integration tests against a local or mocked Graphiti service.

### Acceptance Criteria

* memory operations execute against Graphiti, not in-memory stub
* scoped retrieval and invalidation work with real backend

### Dependencies

TASK-028
TASK-029

---

## [x] TASK-060: Implement real OpenClaw integration surface

### Objective

Integrate Loom into OpenClaw as a real plugin/adapter.

### Work

* Implement OpenClaw-compatible ingress contract.
* Support request ingress, progress streaming, and final response pushback.
* Add adapter config for endpoint registration and auth.
* Add end-to-end tests with OpenClaw-compatible payloads.

### Acceptance Criteria

* `/ff ...` requests can flow from OpenClaw to Loom in real integration mode
* progress and final status are visible in OpenClaw session flow

### Dependencies

TASK-038

---

## [x] TASK-061: Integrate OpenAI Agents SDK for participant execution

### Objective

Move participant execution from placeholder logic to real model-backed execution.

### Work

* Add OpenAI Agents SDK dependency.
* Implement participant runtime bindings using role + prompt profile + tools.
* Add model/provider configuration per environment.
* Add deterministic fallback/mocking mode for tests.
* Add token/cost accounting and logging hooks.

### Acceptance Criteria

* step execution can run with real model calls through configured provider
* prompt profiles and role policies are applied during execution

### Dependencies

TASK-023
TASK-043

---

## [x] TASK-062: Integrate LangSmith tracing backend

### Objective

Emit real traces/spans/events to LangSmith.

### Work

* Replace placeholder adapter with LangSmith SDK integration.
* Map task lifecycle and steps to traces and spans.
* Attach metadata: workflow/version/role/participant/policies.
* Add toggleable local mode when LangSmith is unavailable.

### Acceptance Criteria

* live runs are visible in LangSmith with step-level traceability

### Dependencies

TASK-034

---

## [x] TASK-063: Implement real OpenCode integration for context assembly

### Objective

Use actual OpenCode APIs/CLI for repository context retrieval.

### Work

* Replace local file scan fallback with OpenCode integration path.
* Add query scopes for docs/files/PR-linked artifacts.
* Add caching and invalidation for large repo contexts.

### Acceptance Criteria

* docs workflows retrieve context via OpenCode integration path in production mode

### Dependencies

TASK-044

---

# 24. Phase 17 — Production Runtime and Security Hardening

## [x] TASK-064: Add production config and secret management

### Objective

Support secure runtime config for production environments.

### Work

* Add typed config for all external integrations.
* Add secret loading via env + optional secret manager.
* Add startup validation for required secrets.
* Add redaction of secrets in logs/events/traces.

### Acceptance Criteria

* app fails fast if required production secrets/config are missing
* secrets never appear in logs or API responses

### Dependencies

TASK-055
TASK-059
TASK-061
TASK-062

---

## [x] TASK-065: Add PostgreSQL production persistence and migration strategy

### Objective

Support production-grade persistence backend and migrations.

### Work

* Add PostgreSQL engine configuration.
* Add Alembic revisions for all tables and constraints.
* Add migration CI checks and rollback-tested migration scripts.
* Add retention and backup guidance.

### Acceptance Criteria

* production DB migrations are reproducible and reversible
* task/workflow/event integrity constraints are enforced in DB

### Dependencies

TASK-004

---

## [x] TASK-066: Add queue-backed async workers for long-running steps

### Objective

Separate API ingress latency from long-running workflow execution.

### Work

* Add worker execution mode and queue transport.
* Implement job status persistence and idempotency keys.
* Add retry/backoff/dead-letter strategy.
* Ensure policy and state-machine invariants hold in async mode.

### Acceptance Criteria

* long-running tasks can execute asynchronously and recover from worker restarts

### Dependencies

TASK-026
TASK-033

---

## [x] TASK-067: Enforce runtime command/tool safety controls

### Objective

Prevent unsafe tool execution in production.

### Work

* Add explicit tool allowlists/denylists by role/policy.
* Add filesystem/network sandbox policy mapping.
* Add command audit trails with policy decisions.
* Add secure defaults for destructive actions.

### Acceptance Criteria

* unsafe commands are blocked and auditable
* policy enforcement is deterministic and test-covered

### Dependencies

TASK-027
TASK-039

---

## [x] TASK-068: Add API authentication and authorization

### Objective

Protect ingress and admin endpoints in production.

### Work

* Add auth middleware (token or OIDC/JWT mode).
* Add role-based authorization for admin operations.
* Add audit events for authn/authz success/failure.

### Acceptance Criteria

* unauthorized requests are rejected consistently
* admin operations are protected by explicit permissions

### Dependencies

TASK-039

---

## [x] TASK-069: Container and supply-chain hardening

### Objective

Harden build artifacts for production deployment.

### Work

* Pin system packages and Python dependencies.
* Add image scanning and SBOM generation.
* Drop unnecessary Linux capabilities and enforce non-root runtime.
* Add provenance metadata in CI artifacts.

### Acceptance Criteria

* release image passes vulnerability and policy gates

### Dependencies

TASK-053

---

## [x] TASK-070: CI/CD pipeline for release promotion

### Objective

Build a repeatable release pipeline.

### Work

* Add CI jobs for lint/type/tests/integration/e2e.
* Add artifact build and image publish steps.
* Add environment promotion workflow (dev -> staging -> prod).
* Add release notes/changelog generation.

### Acceptance Criteria

* every production release is built and validated through CI/CD gates

### Dependencies

TASK-050
TASK-051
TASK-052
TASK-069

---

# 25. Phase 18 — Production Readiness Validation

## [x] TASK-071: Real integration end-to-end test suite

### Objective

Validate Loom against live/staging integrations.

### Work

* Run end-to-end workflows against Graphiti/OpenClaw/OpenAI/LangSmith staging.
* Add smoke tests for each external connector.
* Add failure-injection cases for partial outages and retries.

### Acceptance Criteria

* at least one full docs workflow succeeds in staging with real integrations
* failure modes are handled with explicit blocked/failed outcomes

### Dependencies

TASK-059
TASK-060
TASK-061
TASK-062
TASK-063

---

## [x] TASK-072: Performance, load, and cost validation

### Objective

Establish production SLO and cost baselines.

### Work

* Add load-test scenarios for concurrent `/ff` requests.
* Measure latency by phase: triage, compile, execution, persistence.
* Add model token/cost telemetry and budget guardrails.
* Tune worker concurrency and DB settings.

### Acceptance Criteria

* defined throughput/latency targets are met in staging
* cost reports are generated per workflow run

### Dependencies

TASK-066
TASK-071

---

## [x] TASK-073: Security and compliance validation

### Objective

Validate production security posture.

### Work

* Add SAST/DAST/dependency scanning in CI.
* Add threat model and mitigation checklist.
* Add PII handling rules for memory/traces/logs.
* Add penetration-test findings and remediation tracking.

### Acceptance Criteria

* critical/high findings are remediated or explicitly risk-accepted

### Dependencies

TASK-064
TASK-067
TASK-068
TASK-069

---

## [x] TASK-074: Operational runbooks and SRE readiness

### Objective

Make Loom operable in production.

### Work

* Define SLO/SLI and alert thresholds.
* Add dashboards for task states, failures, queue depth, connector health.
* Write runbooks for incidents: provider outage, DB outage, stuck workflows.
* Define backup/restore and disaster-recovery procedure.

### Acceptance Criteria

* on-call team can detect, triage, and recover common failure modes

### Dependencies

TASK-070
TASK-071

---

## [x] TASK-075: Final production go-live gate

### Objective

Authorize production launch through explicit readiness criteria.

### Work

* Create go-live checklist across architecture, security, reliability, and operations.
* Require signoff from engineering, security, and platform owners.
* Freeze and tag release candidate.

### Acceptance Criteria

* go-live checklist is fully green and signed off
* release candidate is deployable with rollback procedure

### Dependencies

TASK-072
TASK-073
TASK-074

---

# 26. Suggested Production Build Order Addendum

After TASK-058, execute:

1. TASK-059 -> TASK-063
2. TASK-064 -> TASK-070
3. TASK-071 -> TASK-075

---

# 27. Production Reality Cut (Minimum for Real Deployment)

A practical minimum before production deployment:

* TASK-059 Graphiti real integration
* TASK-060 OpenClaw real integration
* TASK-061 OpenAI Agents SDK integration
* TASK-062 LangSmith integration
* TASK-064 secret/config hardening
* TASK-065 PostgreSQL + migrations
* TASK-067 tool safety controls
* TASK-068 API authn/authz
* TASK-069 container hardening
* TASK-070 CI/CD release gates
* TASK-071 real integration e2e
* TASK-073 security validation
* TASK-074 operational runbooks
* TASK-075 go-live gate

Everything else can layer in parallel but these are the minimum deployment-critical items.

---

# 28. Phase 19 — GUI Productization (Production-Ready Control Plane)

## [x] TASK-076: Define GUI information architecture and API contracts

### Objective

Define a stable control-plane IA for all first-class Loom entities.

### Work

* Define GUI sections for:
  * workflows
  * agents/roles
  * capabilities
  * policies
  * prompt profiles
  * domain packs
  * schedules
  * tasks/runs
  * traces/events
  * memory scopes
  * integrations status
* Define API contract map (`GET/POST/PATCH/DELETE`) for each entity.
* Define canonical frontend DTOs and server response envelopes.

### Acceptance Criteria

* API and GUI entity maps are documented and implemented consistently
* no hidden entity operations require direct DB access

### Dependencies

TASK-039
TASK-058

---

## [x] TASK-077: Add production-grade GUI authn/authz

### Objective

Secure GUI and API operations for production usage.

### Work

* Add session/token auth for GUI.
* Add role-based authorization for action classes:
  * viewer
  * operator
  * admin
* Restrict dangerous actions (activate/deprecate, invalidation, promotion, deletes) to admin/operator policy.
* Add auth failure audit events.

### Acceptance Criteria

* unauthorized GUI/API actions are denied with clear errors
* permissions map is explicit, tested, and documented

### Dependencies

TASK-068

---

## [x] TASK-078: Implement secure frontend transport posture

### Objective

Harden browser surface for production.

### Work

* Add CSRF protection strategy for mutating requests.
* Add CSP and security headers.
* Add cookie/session hardening where applicable.
* Add XSS-safe rendering practices in workflow markdown/editor views.

### Acceptance Criteria

* security headers are present and validated
* mutating actions are CSRF-safe

### Dependencies

TASK-077

---

## [x] TASK-079: Schema-driven CRUD forms with strong validation

### Objective

Make CRUD reliable and safe for operators.

### Work

* Build schema-driven forms for all entities.
* Add field-level validation and user-facing error mapping.
* Add optimistic + pessimistic update modes where appropriate.
* Add conflict handling for versioned entities.

### Acceptance Criteria

* CRUD operations can be performed from GUI without malformed payloads
* validation errors are actionable and non-ambiguous

### Dependencies

TASK-076

---

## [x] TASK-080: Workflow version lifecycle UX

### Objective

Enable complete workflow lifecycle from GUI.

### Work

* Add create draft / edit draft / compile / validate / activate / deprecate / archive actions.
* Add workflow version history timeline.
* Add side-by-side markdown diff and IR diff view.
* Add rollback-to-previous-active action with safeguards.

### Acceptance Criteria

* workflow lifecycle can be managed end-to-end in GUI
* active version switching is explicit and auditable

### Dependencies

TASK-015
TASK-079

---

## [x] TASK-081: Agent builder UX (role + prompt + capabilities + policies)

### Objective

Enable operator-defined agent profiles from GUI.

### Work

* Add agent builder panel that composes:
  * role definition
  * capability bindings
  * prompt profile
  * policy bindings
  * memory visibility
* Add compatibility checks against workflows referencing the role.

### Acceptance Criteria

* users can create/update agent definitions without manual YAML edits
* invalid role-capability-policy combinations are blocked pre-save

### Dependencies

TASK-006
TASK-007
TASK-009
TASK-008
TASK-079

---

## [x] TASK-082: Run console with real-time task execution updates

### Objective

Provide operator-grade visibility during execution.

### Work

* Add run console with streaming updates (SSE/WebSocket).
* Show state transitions, active step, participants, policy checks, and outcomes.
* Support run controls:
  * trigger
  * retry step (if policy allows)
  * mark blocked/failed with reason

### Acceptance Criteria

* operators can monitor and control active runs from GUI
* console reflects live task progression with trace correlation

### Dependencies

TASK-033
TASK-034
TASK-066

---

## [x] TASK-083: Topology and memory views in GUI

### Objective

Expose architecture-level system understanding to operators.

### Work

* Add topology visualization pane (Mermaid rendered).
* Add memory scope explorer by workflow/role/entity/task lineage.
* Add memory invalidation controls with confirmation workflows.

### Acceptance Criteria

* operators can inspect current topology and memory scopes visually
* memory actions are explicit and auditable

### Dependencies

TASK-035
TASK-030
TASK-032

---

## [x] TASK-084: Audit and incident panel

### Objective

Centralize operational forensic visibility.

### Work

* Add searchable audit/events panel.
* Add filters by task/workflow/role/event severity/time range.
* Add incident marker/export for postmortems.

### Acceptance Criteria

* operators can investigate failures without raw DB access

### Dependencies

TASK-033
TASK-074

---

## [x] TASK-085: UX quality gates (a11y, responsiveness, reliability)

### Objective

Ensure GUI quality for production operators.

### Work

* Add responsive layouts for laptop and desktop.
* Add accessibility checks (keyboard nav, labels, contrast).
* Add empty/loading/error states for all panels.
* Add non-destructive confirmations for dangerous actions.

### Acceptance Criteria

* GUI is usable, accessible, and predictable in standard operator contexts

### Dependencies

TASK-079

---

## [x] TASK-086: GUI test strategy and release gates

### Objective

Ensure GUI behavior remains stable during iteration.

### Work

* Add frontend unit tests for state/actions.
* Add e2e tests for critical flows:
  * publish workflow
  * create/update agent
  * run task
  * inspect trace
  * invalidate memory
* Add GUI quality checks to release pipeline.

### Acceptance Criteria

* regressions in primary GUI flows are caught pre-release

### Dependencies

TASK-085
TASK-070

---

# 29. Phase 20 — Tool Bootstrap via flake.nix and Local Stack Orchestration

## [x] TASK-087: Define external tool bootstrap matrix and pinning policy

### Objective

Define exactly how each external tool is obtained, versioned, and verified.

### Work

* Create matrix for:
  * OpenClaw
  * OpenCode
  * Graphiti client/runtime
  * OpenAI SDK
  * LangSmith SDK
  * gh/git/PlantUML/node/java
* Define source strategy per tool:
  * Nix package
  * flake input
  * containerized sidecar
  * pip package
* Define pinning + upgrade cadence + compatibility constraints.

### Acceptance Criteria

* every dependency has a deterministic source and versioning strategy

### Dependencies

TASK-059
TASK-060
TASK-061
TASK-062
TASK-063

---

## [x] TASK-088: Extend flake.nix with pinned toolchain inputs and wrappers

### Objective

Make `nix develop` sufficient to run Loom + integrations locally.

### Work

* Add/pin required tool inputs.
* Add shell wrappers/helpers for common tool commands.
* Add platform-specific notes for Linux/macOS differences.
* Add command verification on shell entry.

### Acceptance Criteria

* `nix develop` provides all required CLI/runtime dependencies for local stack

### Dependencies

TASK-087

---

## [x] TASK-089: Build local stack bootstrap scripts

### Objective

Automate local environment preparation and connector wiring.

### Work

* Add scripts to:
  * initialize `.env.local` template
  * validate required env vars
  * run migrations
  * load docs pack
  * verify connector availability
* Add `make` or script entrypoints for one-command startup.

### Acceptance Criteria

* new developer can bootstrap local Loom stack with one command

### Dependencies

TASK-088
TASK-065

---

## [x] TASK-090: Add optional local integration stack (docker-compose)

### Objective

Run Loom with local companion services for integration testing.

### Work

* Add compose stack for:
  * Loom app
  * optional Graphiti service (or mock)
  * optional tracing sink
  * SQLite/PG mode selection
* Add documented profiles for minimal vs full integration mode.

### Acceptance Criteria

* `docker compose` can run a usable local integration stack

### Dependencies

TASK-089

---

## [x] TASK-091: Connector health and handshake orchestration

### Objective

Ensure Loom validates external dependencies at startup and runtime.

### Work

* Add health probes for each connector.
* Add startup handshake checks with actionable diagnostics.
* Add degraded-mode behavior when optional integrations are unavailable.

### Acceptance Criteria

* integration readiness is visible and deterministic before task execution

### Dependencies

TASK-090

---

## [x] TASK-092: Auto-bootstrap integration bindings in Loom

### Objective

Reduce manual wiring to run integrated workflows.

### Work

* Add connector binding registry initialization from config.
* Add default binding profiles (`local`, `staging`, `prod`).
* Add explicit config conflict detection.

### Acceptance Criteria

* Loom starts with coherent integration bindings from environment/profile

### Dependencies

TASK-091
TASK-010

---

## [x] TASK-093: Toolchain conformance tests

### Objective

Verify bootstrap and integration correctness continuously.

### Work

* Add tests for:
  * flake environment readiness
  * docker stack readiness
  * connector handshake correctness
  * local bootstrap scripts idempotency

### Acceptance Criteria

* bootstrap regressions fail fast in local and CI contexts

### Dependencies

TASK-086
TASK-092

---

# 30. Phase 21 — Local Operator Experience Completion

## [x] TASK-094: End-to-end “create your own workflow in GUI” golden path

### Objective

Guarantee local operator success with zero manual backend edits.

### Work

* Define and test golden flow:
  1. launch Loom via Docker or nix
  2. open GUI
  3. create role/agent
  4. create capabilities/policies/prompts
  5. publish workflow markdown
  6. run task and observe trace
* Add guided UI hints and defaults for this flow.

### Acceptance Criteria

* user can create and run custom agentic workflow from GUI in local mode

### Dependencies

TASK-081
TASK-082
TASK-092

---

## [x] TASK-095: Final local bootstrap docs and troubleshooting guide

### Objective

Make local-first usage self-serve and reliable.

### Work

* Document Docker path and Nix path side-by-side.
* Add troubleshooting for missing tools, auth issues, connector failures.
* Add common error playbook and quick-fix commands.

### Acceptance Criteria

* first-time user can get Loom + GUI + integrations running locally without engineering intervention

### Dependencies

TASK-094
TASK-093

---

# 31. Suggested Build Order Addendum (GUI + Bootstrap)

After TASK-075, execute:

1. TASK-076 -> TASK-086
2. TASK-087 -> TASK-093
3. TASK-094 -> TASK-095

---

# 32. Local-First Reality Cut (GUI + Tool Bootstrap)

Minimum to satisfy local-first operator experience:

* TASK-076
* TASK-079
* TASK-080
* TASK-081
* TASK-082
* TASK-087
* TASK-088
* TASK-089
* TASK-091
* TASK-092
* TASK-094
* TASK-095

These tasks ensure you can use Docker or `nix develop` to run Loom, manage entities in GUI, and execute custom workflows locally.

---

# 33. Phase 22 — LiteLLM-First Model Routing Control Plane

## [x] TASK-096: Add model-provider/model/service-binding core entities

### Objective

Introduce first-class model routing entities for provider, model catalog, and service bindings.

### Work

* Add canonical schemas:
  * model provider
  * model definition
  * service-to-model binding
* Add registries and persistence wiring for these entities.
* Add cross-entity validation (provider exists for model, model exists for service binding).

### Acceptance Criteria

* entities are persisted and retrievable via registry APIs
* invalid cross references are rejected

### Dependencies

TASK-003
TASK-004

---

## [x] TASK-097: Integrate LiteLLM-compatible runtime model routing

### Objective

Route execution services to configured models through LiteLLM-compatible settings and bindings.

### Work

* Add LiteLLM runtime settings and validation.
* Add resolver service for `service_id -> provider -> model`.
* Wire step execution to use resolved model/base URL/API key.
* Add safe fallback behavior when routing is unavailable.

### Acceptance Criteria

* `step_execution` resolves and uses configured LiteLLM route
* routing metadata is observable without exposing secrets

### Dependencies

TASK-096

---

## [x] TASK-098: Add GUI/API CRUD for model routing entities

### Objective

Allow operators to manage LiteLLM routing end-to-end from the control plane.

### Work

* Add UI API endpoints for:
  * model providers
  * models
  * service bindings
  * service route resolution preview
* Add GUI panels and actions for CRUD + resolve.
* Add guardrails for delete conflicts.

### Acceptance Criteria

* operator can create/edit/delete providers, models, and bindings in GUI
* route resolution is visible in GUI/API

### Dependencies

TASK-096
TASK-097

---

## [x] TASK-099: Extend local bootstrap/docs for LiteLLM

### Objective

Make LiteLLM setup discoverable and local-first.

### Work

* Add LiteLLM env vars to local bootstrap templates.
* Document LiteLLM routing workflow in README/runbooks.
* Expose routing status in integration status output.

### Acceptance Criteria

* new users can configure LiteLLM with documented env vars
* integration status clearly reports routing setup

### Dependencies

TASK-097
TASK-098

---

## [x] TASK-100: Add verification for model routing and LiteLLM path

### Objective

Protect model routing behavior from regressions.

### Work

* Add unit/integration/e2e tests for:
  * registry CRUD and validation
  * runtime routing resolution
  * UI API CRUD and resolve flow
* Include validation checks in local test suite.

### Acceptance Criteria

* test suite fails on routing regressions
* LiteLLM path is covered in automated tests

### Dependencies

TASK-098
TASK-099
