# PRD.md

# Loom

**Working name:** Loom
**Category:** Generic workflow-first multi-agent orchestration kernel
**Primary first-party application pack:** Docs Pack
**Initial use case:** HyperSwitch documentation authoring, enhancement, PR review addressal, and PR promotion through natural-language task ingress

---

# 1. Executive Summary

Loom is a **generic orchestration kernel** that brings structure, policy, workflow enforcement, memory, and runtime coordination to otherwise chaotic multi-agent systems.

It is **not** a docs-specific product.
It is **not** a hardcoded collection of agent classes.
It is **not** a fixed set of workflows implemented directly in Python.

Instead, Loom is a **thin Python runtime** that:

* accepts natural-language requests through `/ff ...` on top of OpenClaw,
* classifies them into supported workflows,
* enforces execution through registered workflow definitions,
* resolves runtime participants dynamically from registry data,
* scopes and persists memory,
* coordinates collaborative step execution,
* applies policies and permissions,
* compiles natural-language workflow definitions into validated executable IR,
* and exposes observability, topology, and administration.

Loom treats the following as **data**, not bespoke code:

* workflows,
* roles,
* participants,
* capabilities,
* policies,
* prompt profiles,
* domain packs,
* memory scopes,
* schedules,
* runtime bindings.

The first application of Loom is a **Docs Pack** for HyperSwitch documentation maintenance.
That pack will use Loom’s generic runtime to implement:

1. Task Authoring Workflow
2. Development Workflow
3. PR Review Addressal Workflow
4. PR Promotion Workflow

The end-user experience remains simple:

* `/ff enhance these docs <url>`
* `/ff address comments on PR 482`
* `/ff promote PR 482 if checks are green`

The user does **not** choose the workflow manually.
Loom selects the workflow when possible, or returns an explicit unsupported / insufficient-context response.

---

# 2. Problem Statement

Modern multi-agent systems are powerful but tend to degrade into loosely governed conversational chaos.
Even strong frameworks often leave too much implicit:

* workflow selection is ad hoc,
* participant responsibilities are hardcoded,
* memory is poorly scoped,
* execution is difficult to audit,
* step ownership is unclear,
* natural-language intent is not reliably tied to enforceable execution,
* and domain applications become tightly coupled to framework-specific code.

For the user’s immediate application, this problem appears in documentation maintenance for a complex microservice-based fintech system:

* multiple repositories,
* multiple domains of truth,
* many possible task types,
* need for correctness, review, traceability, and PR-based delivery,
* requirement to add or evolve participants and workflows over time.

However, the deeper problem is broader:

> There is no minimal generic kernel that takes natural-language requests, maps them to governed workflows, resolves runtime participants dynamically, and enforces structure while remaining domain-agnostic.

Loom exists to solve that broader problem.

---

# 3. Vision

Loom should become a **minimal orchestration substrate for governed agentic execution**.

It should feel like this:

* humans describe tasks naturally,
* workflows are authored naturally,
* Loom converts those into governed execution,
* participants are resolved dynamically,
* memory is scoped and useful,
* the runtime remains generic,
* domain-specific behavior comes from domain packs,
* and the orchestrator stays thin.

Loom should enforce the principle:

> No task is allowed to execute outside a workflow.

And also:

> No workflow, participant type, or domain should require bespoke hardcoded Python modules unless absolutely necessary.

---

# 4. Product Principles

## 4.1 Workflow-first, always

Every task must map to a registered workflow before execution starts.
If no workflow matches, the request must be rejected cleanly.

## 4.2 Natural language is for humans; validated IR is for machines

Humans author workflows in structured markdown.
Loom compiles them into a machine-friendly IR.
The markdown remains the source of truth.

## 4.3 Generic kernel, domain packs on top

The kernel should remain domain-agnostic.
Docs is just the first application pack.

## 4.4 Registry-driven, not code-driven

Roles, workflows, policies, capabilities, and prompt profiles should be data stored in registries.

## 4.5 Thin orchestration layer

Loom should not become a giant framework inside the application.
It should mainly:

* classify,
* route,
* coordinate,
* validate,
* enforce,
* persist,
* observe.

## 4.6 Ownership is explicit

Every workflow step must have explicit ownership.
A step may also include collaborators and spawning rules.

## 4.7 Memory must be scoped

Memory is useful only when it is scoped properly by workflow version, domain pack, entity, role, and task lineage.

## 4.8 Runtime participants are dynamic

The system should not assume hardcoded singleton agents.
Work is performed by runtime-resolved participant instances.

## 4.9 Policies are first-class

Permissions, approvals, write restrictions, merge restrictions, and memory visibility rules must be explicit and enforceable.

## 4.10 Traceability over magic

Every task, step, handoff, decision, failure, block, and outcome should be inspectable.

---

# 5. Goals

## 5.1 Primary Goals

1. Build a **generic orchestration kernel** in Python.
2. Support **natural-language task ingress** through OpenClaw.
3. Support **natural-language workflow authoring** in markdown.
4. Compile workflows into validated executable IR.
5. Enforce all execution through registered workflows.
6. Resolve runtime participants from role/capability registry data.
7. Support scoped persistent memory.
8. Support collaborative multi-participant steps.
9. Support live topology rendering.
10. Support domain-specific application packs without modifying kernel internals.
11. Support the Docs Pack as the first real production use case.

## 5.2 Secondary Goals

1. Provide strong operator UX through CLI first.
2. Make it easy to add, update, retire, or delete workflows.
3. Make it easy to add, update, retire, or delete roles and participant definitions.
4. Provide strong observability and debugging.
5. Make local development easy through Docker and Nix.

---

# 6. Non-Goals

Loom v1 will **not** aim to:

1. be a no-code drag-and-drop workflow builder,
2. support arbitrary autonomous background execution without workflow registration,
3. auto-merge PRs by default,
4. support every possible domain out of the box,
5. replace OpenClaw, LangGraph, Graphiti, OpenAI Agents SDK, or OpenCode,
6. build a fully general agent society simulator,
7. support fine-grained multi-tenant enterprise governance in v1,
8. guarantee zero hallucination without validation,
9. use specialized hardcoded Python classes for each role as the primary design.

---

# 7. Personas

## 7.1 Primary Persona: Operator

A technically capable user who interacts with Loom via `/ff ...` through OpenClaw.
This user wants natural-language ingress, task status, and predictable outcomes.

## 7.2 Administrator

A user who manages workflows, roles, policies, memory scopes, schedules, and domain packs.

## 7.3 Domain Maintainer

A user who authors or edits workflow markdown and domain-pack definitions.
This user should not need to write low-level runtime code.

## 7.4 Coding Agent Consumer

A downstream automated coding/implementation agent that receives PRD/architecture/tasks artifacts to implement Loom.

---

# 8. User Problems to Solve

## 8.1 “I want natural language, not rigid command syntax.”

Users should be able to issue `/ff ...` requests in natural language.

## 8.2 “I do not want workflows hardcoded in Python.”

Workflows must be authored in structured markdown and compiled automatically.

## 8.3 “I do not want roles hardcoded as separate files.”

Roles and runtime participant definitions must live in registries.

## 8.4 “I want workflows enforced, not just suggested.”

No task should bypass workflow resolution.

## 8.5 “I want a generic runtime, not a docs-only app.”

Docs must be modeled as a first domain pack, not as the kernel itself.

## 8.6 “I want multiple participants on the same step.”

A workflow step may have owners, collaborators, and spawn rules.

## 8.7 “I want memory, but not stale or wrong memory.”

Memory must be scoped, version-aware, and support forgetting when workflows evolve.

## 8.8 “I want extensibility without bespoke code.”

New workflows, participants, and domains should mostly be added through data/configuration.

---

# 9. Product Scope

## 9.1 In Scope for v1

### Kernel

* Natural-language task ingestion through `/ff ...`
* Workflow classification and selection
* Workflow registry
* Role/participant registry
* Capability registry
* Prompt profile registry
* Policy registry
* Domain pack registry
* Memory scoping and persistence
* Workflow compilation pipeline (markdown → executable IR)
* Runtime execution coordination
* Topology generation
* Schedules / cron support
* Observability and tracing hooks

### Docs Pack

* HyperSwitch documentation-related task classification
* Repo context gathering
* PR operations via git + gh
* Diagram generation support via PlantUML
* Documentation verification
* Initial four workflows

## 9.2 Out of Scope for v1

* Full GUI-based task authoring
* Production-grade enterprise RBAC
* Visual workflow editor
* Fully automatic promotion/merge without controlled policy
* Arbitrary third-party domain packs bundled by default

---

# 10. High-Level Product Shape

Loom should conceptually consist of the following layers:

1. **Ingress Layer**
   Receives natural-language requests through OpenClaw.

2. **Triage Layer**
   Classifies requests, extracts entities, chooses a workflow or rejects the request.

3. **Kernel Layer**
   Owns workflow enforcement, state management, participant resolution, policy enforcement, memory scope resolution, and execution coordination.

4. **Compilation Layer**
   Converts workflow markdown into validated executable IR.

5. **Execution Layer**
   Runs workflow steps through runtime participant instances, connectors, validations, and collaborative execution.

6. **Registry Layer**
   Stores workflows, roles, participants, capabilities, policies, prompt profiles, schedules, and domain packs.

7. **Memory Layer**
   Stores task lineage, episodic memory, semantic memory, and scoped retrieval.

8. **Observability Layer**
   Stores traces, task histories, runtime events, and topology snapshots.

9. **Domain Pack Layer**
   Docs Pack and future packs.

---

# 11. Core Product Concepts

## 11.1 Task

A task is a single requested unit of work entering the system.
A task must always map to one workflow version before execution.

### Task fields

* task_id
* raw_request
* normalized_request
* workflow_id
* workflow_version
* domain_pack
* current_status
* current_step_id
* created_at
* updated_at
* linked_entities
* memory_scope_refs
* execution_refs
* result_summary

## 11.2 Workflow Definition

A workflow definition is the human-authored source-of-truth markdown document describing:

* purpose,
* trigger conditions,
* required inputs,
* ordered steps,
* completion criteria,
* blocked conditions,
* failure conditions,
* rules.

## 11.3 Compiled Workflow IR

A validated low-level machine-readable form derived from the markdown workflow.
This is not hand-authored by operators.

## 11.4 Workflow Execution

A live runtime instance of a task moving through a specific workflow version.

## 11.5 Role Definition

A role is an abstract responsibility profile.
Examples in Docs Pack include:

* docs_ops
* development
* technical_writer
* product_correctness
* diagramming
* devex
* qa
* infra
* marketing

The kernel does not hardcode these.

## 11.6 Runtime Participant

A concrete runtime instance resolved from a role definition.
There may be one or many instances per role.

## 11.7 Capability

A generic named ability required for step completion.
Examples:

* pr_read
* pr_update
* context_build
* review_analysis
* content_update
* validation
* diagram_generation
* developer_review
* product_review

## 11.8 Ownership

Each step must identify who owns the step.
Ownership is expressed in terms of roles, not hardcoded classes.

## 11.9 Participation

Additional roles may collaborate on a step.

## 11.10 Spawn Strategy

A step may permit one or many runtime participant instances.
Spawn policies define collaboration structure.

## 11.11 Memory Scope

A structured boundary defining what memory is visible and writable during execution.

## 11.12 Domain Pack

A pluggable application package built on top of the kernel.
A domain pack contributes:

* workflow definitions,
* role definitions,
* capability bindings,
* prompt profiles,
* validation rules,
* connectors,
* topology semantics,
* request classifiers.

Docs Pack is the first such pack.

---

# 12. Functional Requirements

## 12.1 Natural-Language Task Ingress

### Requirement

Users must be able to submit tasks in natural language through `/ff ...` on top of OpenClaw.

### Expected behavior

* receive free-form request text,
* classify intent,
* extract relevant entities,
* select a valid workflow if possible,
* otherwise return a clear unsupported / blocked response.

### Examples

* `/ff enhance these docs <url>`
* `/ff add docs for payout routing`
* `/ff address comments on PR 842`
* `/ff promote PR 842 if checks are green`

## 12.2 Workflow Selection

### Requirement

Loom must determine which registered workflow applies to a task.

### Rules

* selection must use classifier + workflow metadata,
* if confidence is too low, reject or ask for minimal clarification,
* if no workflow exists, return unsupported.

## 12.3 Workflow Authoring in Natural Language

### Requirement

Workflow definitions must be authored in structured markdown, not low-level YAML or Python.

### Minimum required sections

* Title
* Purpose
* Trigger
* Required Inputs
* Steps
* Completion Criteria
* Blocked Conditions
* Failure Conditions
* Rules

## 12.4 Workflow Compilation

### Requirement

Loom must compile workflow markdown into low-level executable IR using an LLM-assisted compiler and strict validation.

### Rules

* markdown is source of truth,
* compiled IR is generated artifact,
* compiled IR must never be executed without validation,
* if compilation fails, the workflow remains draft/inactive.

## 12.5 Workflow Versioning

### Requirement

Each workflow must be versioned.

### Rules

* updates create a new version,
* active version is explicit,
* deprecated versions remain visible for audit,
* new tasks use only active versions,
* memory retrieval must prefer active workflow scopes.

## 12.6 Registry-Driven Runtime

### Requirement

Loom must load behavior from registries instead of bespoke Python classes wherever possible.

### Registries required

* Workflow Registry
* Role Registry
* Capability Registry
* Prompt Profile Registry
* Policy Registry
* Domain Pack Registry
* Schedule Registry
* Participant Runtime Registry

## 12.7 Step Ownership and Collaboration

### Requirement

Every workflow step must define ownership.
A step may also define collaborators and spawn behavior.

### Required concepts per compiled step

* id
* title
* owned_by
* participants
* capabilities_required
* spawn
* inputs
* outputs
* completion
* transitions
* rules

## 12.8 Memory

### Requirement

Loom must support scoped memory for execution and learning.

### Memory types

* Working memory
* Episodic memory
* Semantic memory
* Consolidated memory

### Memory scoping dimensions

* workflow_id
* workflow_version
* domain_pack
* task lineage
* linked entities (repo/doc/PR/etc.)
* role scope
* project scope

## 12.9 Forgetting and Memory Invalidation

### Requirement

When workflows evolve, Loom must support soft forgetting and controlled hard forgetting.

### Rules

* old workflow memory can be hidden from default retrieval,
* hard deletion may be initiated explicitly,
* deletion should be audited,
* rebuild/reconsolidation may be required after deletion.

## 12.10 Policies

### Requirement

Loom must support explicit policy enforcement.

### Policy examples

* raise PR only
* no direct merge
* require approval before promotion
* restrict memory access by scope
* restrict write actions to certain roles
* permit or deny certain capabilities

## 12.11 Runtime Coordination

### Requirement

Loom must coordinate execution step by step and keep explicit task state.

### Task state must support

* current step
* completed steps
* blocked status
* failure status
* retries
* step outputs
* active participants
* transition history

## 12.12 Topology Rendering

### Requirement

Loom must expose a real-time topology of active roles, runtime participants, and task associations.

### Initial rendering format

* Mermaid

## 12.13 Schedules / Cron

### Requirement

Loom must support schedules that trigger workflows or maintenance actions.

### Initial examples

* nightly memory consolidation
* stale PR sweep
* docs freshness scan
* topology regeneration

## 12.14 Observability

### Requirement

Every execution must produce traceable runtime events.

### At minimum

* task creation
* workflow selection
* workflow version used
* step entered
* step completed
* step blocked
* step failed
* participant resolution
* memory reads/writes
* schedule trigger
* final outcome

---

# 13. Docs Pack (First Domain Pack)

Docs Pack is the first production application built on Loom.
It must prove the kernel is generic while delivering immediate value.

## 13.1 Purpose

Use Loom to maintain, enhance, review, and promote documentation through PR-driven workflows.

## 13.2 Initial workflows

1. Task Authoring Workflow
2. Development Workflow
3. PR Review Addressal Workflow
4. PR Promotion Workflow

## 13.3 Initial roles contributed by Docs Pack

* development
* docs_ops
* technical_writer
* product_correctness
* diagramming
* devex
* qa
* infra
* marketing

These roles are registry entries, not Python subclasses.

## 13.4 Initial capabilities contributed by Docs Pack

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

## 13.5 Initial policies contributed by Docs Pack

* raise_pr_only = true
* direct_merge = false
* promotion_requires_policy_pass = true

---

# 14. Natural-Language Workflow Definition Model

## 14.1 Authoring format

Workflows must be written as markdown with structured sections.

## 14.2 Example structure

```md
# Workflow: Task Authoring

## Purpose
Use this workflow when a user wants to create, improve, expand, or clean up documentation.

## Trigger
This workflow should be selected for requests like:
- enhance these docs
- improve this page
- add documentation for this feature
- rewrite this guide

## Required Inputs
- user request
- target document URL or repository
- relevant context
- existing documentation, if any

## Steps
1. Understand the user request and identify the target area.
2. Gather the relevant context from repositories, existing docs, pull requests, and memory.
3. Validate that the intended documentation matches reality.
4. Draft the updated or new documentation.
5. Add or update diagrams if the topic benefits from them.
6. Review the documentation for clarity and usability.
7. Run verification checks.
8. Create or update a pull request with the proposed changes.
9. Report the result back to the user.

## Completion Criteria
This workflow is complete when a pull request has been successfully created or updated and all required verification steps have passed.

## Blocked Conditions
This workflow is blocked when:
- the target repository or documentation cannot be identified
- required context cannot be retrieved
- correctness cannot be established
- verification fails and cannot be auto-fixed

## Failure Conditions
This workflow fails when:
- the system cannot classify the request confidently
- a required integration is unavailable
- the repository cannot be updated
- pull request creation fails

## Rules
- Never merge directly.
- Always raise or update a pull request.
- Use memory only from the active workflow version unless explicitly overridden.
```

## 14.3 Compilation expectations

The compiler should extract:

* purpose metadata,
* trigger patterns,
* input hints,
* ordered steps,
* optional branch hints,
* completion criteria,
* blocked/failure terminal conditions,
* workflow rules.

---

# 15. Compiled Workflow IR Model

The compiled IR is not a human-primary authoring layer.
It is the runtime’s validated intermediate representation.

## 15.1 Compiled workflow concepts

* metadata
* selection hints
* normalized inputs
* normalized state
* normalized steps
* terminal states
* completion rules
* policy bindings
* memory bindings

## 15.2 Compiled step concepts

Each step should contain at minimum:

* id
* title
* owned_by
* participants
* capabilities_required
* spawn
* inputs
* outputs
* completion
* transitions
* rules

## 15.3 Notes on ownership

`owned_by` refers to roles, not hardcoded runtime instances.
The kernel resolves runtime participants dynamically from registry data.

## 15.4 Notes on participants

Participants are collaborators, not necessarily co-owners.

## 15.5 Notes on spawn

Spawn describes how many runtime participants may be created and how collaboration should work.

### Possible spawn strategies

* single_owner
* primary_with_support
* parallel_research
* consensus_required
* any_one_can_complete

---

# 16. Role and Participant Model

## 16.1 Role Definition

A role defines a responsibility profile and an allowed set of capabilities, prompts, policies, and memory scopes.

### Example role fields

* role_id
* name
* description
* capability set
* prompt profile defaults
* policy bindings
* memory scope visibility
* domain pack ownership
* runtime spawn constraints

## 16.2 Runtime Participant

A concrete runtime instance resolved from a role.

### Example fields

* participant_id
* role_id
* status
* current_task_refs
* current_step_refs
* execution profile
* available capabilities
* memory scope bindings
* lifecycle timestamps

## 16.3 No bespoke specialized code by default

The preferred implementation is registry-driven role behavior using prompt profiles, capabilities, policies, and domain-pack bindings.
Only true infrastructural extensions should require code.

---

# 17. Capability Model

Capabilities are generic named abilities required for work.
They are not the same as roles.

### Why capabilities exist

Roles describe responsibility.
Capabilities describe what ability is needed.

A role may have many capabilities.
A capability may be shared by many roles.

### Examples

* pr_read
* pr_update
* pr_create
* context_build
* markdown_write
* review_analysis
* validation
* build_check
* developer_review
* product_review

---

# 18. Policy Model

Policies must be explicit, auditable, and enforceable.

## 18.1 Workflow-level policies

Examples:

* no_direct_merge
* approval_required_for_promotion
* active_memory_only
* raise_pr_only

## 18.2 Step-level policies

Examples:

* only certain roles may own this step
* only certain capabilities may be used
* certain collaborators are required

## 18.3 Global policies

Examples:

* unsupported requests must not execute
* invalid compiled workflows cannot be activated
* deprecated workflows cannot receive new tasks

---

# 19. Memory Model

## 19.1 Working Memory

Short-lived state for current task execution.

## 19.2 Episodic Memory

Task-specific memory recorded from runs.

## 19.3 Semantic Memory

Consolidated durable knowledge derived from episodes.

## 19.4 Consolidation / Sleep

A scheduled process that condenses episodic memory into higher-value semantic memory.

## 19.5 Memory visibility rules

Memory should be filtered by:

* active workflow version,
* domain pack,
* task lineage,
* role,
* entity scope.

## 19.6 Forgetting

When workflows are replaced, old workflow memory should by default be excluded from active retrieval.
Explicit hard deletion should be possible through admin controls.

---

# 20. Schedules

Schedules trigger system actions or workflows on time-based rules.

## 20.1 Schedule use cases

* memory consolidation
* stale PR review
* docs freshness checks
* verification sweeps
* topology regeneration

## 20.2 Schedule fields

* schedule_id
* name
* cron expression
* timezone
* enabled
* target workflow or maintenance action
* input payload
* last_run_at
* next_run_at

---

# 21. CLI and User Experience

## 21.1 Task ingress

Users interact through OpenClaw with natural-language `/ff ...`.

### Examples

* `/ff enhance these docs <url>`
* `/ff improve the payout routing guide`
* `/ff address comments on PR 842`
* `/ff promote PR 842`

## 21.2 Admin ingress

Admin operations may use a separate structured command family later, but user task submission remains natural-language-first.

## 21.3 Rejection behavior

If no workflow matches, Loom must return a clear response such as:

* unsupported request,
* insufficient context,
* missing entity,
* inactive workflow,
* blocked by policy.

---

# 22. Success Criteria

Loom v1 is successful if:

1. a user can issue natural-language `/ff ...` requests,
2. Loom reliably selects one of the supported workflows or rejects cleanly,
3. workflows are authored in markdown and compiled automatically,
4. no core workflow needs to be hardcoded as bespoke Python business logic,
5. roles and participants are registry-driven,
6. memory is scoped and useful,
7. live topology is renderable,
8. Docs Pack can produce PR-based outputs predictably,
9. the implementation remains thin and generic.

---

# 23. Risks

## 23.1 Overfitting to Docs Pack

Risk: kernel accidentally becomes docs-specific.
Mitigation: keep domain logic inside domain packs and registries.

## 23.2 Workflow compilation ambiguity

Risk: natural-language workflows compile inconsistently.
Mitigation: use a strict markdown template + validation + draft activation flow.

## 23.3 Registry sprawl

Risk: too many disconnected registry entities.
Mitigation: define clear schemas and naming conventions.

## 23.4 Participant explosion

Risk: too many runtime participants create confusion.
Mitigation: explicit spawn policies and topology visibility.

## 23.5 Memory contamination

Risk: stale or deprecated memory affects new runs.
Mitigation: strict scope filtering and invalidation controls.

## 23.6 Hidden complexity in the kernel

Risk: kernel becomes too heavy.
Mitigation: keep kernel responsibilities narrow and generic.

---

# 24. Open Questions

1. How strict should classifier confidence thresholds be before requesting clarification?
2. Which low-level IR format should be canonical on disk: YAML only, JSON only, or both?
3. Should workflow compilation happen synchronously on update or as a background validation job?
4. How much of topology should reflect inactive role definitions vs only active runtime participants?
5. How should human approvals be modeled in compiled IR?
6. What is the exact retention/deletion model for Graphiti-backed memory in v1?

---

# 25. Proposed v1 Acceptance Scope

For v1, Loom should ship with:

* generic kernel runtime in Python,
* workflow markdown authoring,
* workflow compiler to low-level IR,
* validation pipeline,
* workflow registry,
* role registry,
* capability registry,
* policy registry,
* domain pack registry,
* memory service integration,
* `/ff ...` natural-language ingress through OpenClaw,
* task state persistence,
* live Mermaid topology,
* schedule support,
* Docs Pack with the first four workflows.

---

# 26. Final Product Statement

Loom is a **generic workflow-first orchestration kernel** that converts natural-language requests into governed multi-agent execution using registry-defined workflows, roles, capabilities, memory scopes, policies, and domain packs.

Its first production use case is HyperSwitch documentation, but the kernel itself is intentionally generic, thin, and extensible.

That genericity is the point.
