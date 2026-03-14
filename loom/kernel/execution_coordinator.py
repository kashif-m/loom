from __future__ import annotations

import shutil
from uuid import uuid4

import httpx

from loom.models import Task, TaskStatus


class ExecutionCoordinator:
    def __init__(
        self,
        execution_planner,
        participant_resolver,
        policy_engine,
        step_runner,
        collaborative_step_runner,
        transition_engine,
        event_bus,
        repositories=None,
        state_partition_service=None,
        memory_service=None,
        memory_topology_service=None,
        model_router=None,
        capability_registry=None,
        settings=None,
    ):
        self.execution_planner = execution_planner
        self.participant_resolver = participant_resolver
        self.policy_engine = policy_engine
        self.step_runner = step_runner
        self.collaborative_step_runner = collaborative_step_runner
        self.transition_engine = transition_engine
        self.event_bus = event_bus
        self.repositories = repositories
        self.state_partition_service = state_partition_service
        self.memory_service = memory_service
        self.memory_topology_service = memory_topology_service
        self.model_router = model_router
        self.capability_registry = capability_registry
        self.settings = settings

    def run_task(self, task: Task, global_policy_ids: list[str] | None = None) -> Task:
        if not task.workflow_id or task.workflow_version is None:
            raise ValueError("task has no selected workflow")

        global_policy_ids = global_policy_ids or []
        ir = self.execution_planner.load_ir(task.workflow_id, task.workflow_version)
        preflight = self._preflight_task(task, ir)
        if preflight:
            task.current_status = TaskStatus.blocked
            task.result_summary = f"{preflight['code']}: {preflight['message']}"
            task.execution_refs["preflight"] = preflight
            return task

        current_step = self.execution_planner.first_step(ir)
        task.current_status = TaskStatus.running
        task.current_step_id = current_step.step_id

        step_map = {s.step_id: s for s in ir.steps}
        while task.current_status == TaskStatus.running and task.current_step_id:
            step = step_map[task.current_step_id]
            try:
                participants = self.participant_resolver.resolve(task.task_id, step)
                role_policy_ids = self._role_policy_ids(step.owned_by)

                self.policy_engine.enforce(
                    global_policy_ids,
                    ir.policy_hints,
                    role_policy_ids,
                    step.policy_bindings,
                    {"operation": "step_execute", "task_id": task.task_id, "step_id": step.step_id},
                )

                if len(participants) > 1:
                    outcome, merged = self.collaborative_step_runner.run(task, step, participants)
                else:
                    outcome, merged = self.step_runner.run(task, step, participants[0])

                merged = self._maybe_run_subworkflow(task, step, merged)
                subworkflow_status = (merged.get("subworkflow") or {}).get("status")
                if subworkflow_status and subworkflow_status != TaskStatus.completed.value:
                    outcome = "blocked"

                self.policy_engine.enforce(
                    global_policy_ids,
                    ir.policy_hints,
                    role_policy_ids,
                    step.policy_bindings,
                    {
                        "operation": "state_write",
                        "task_id": task.task_id,
                        "step_id": step.step_id,
                        "actor_role": step.owned_by,
                        "state_partition": (step.memory_hints or {}).get("state_partition", "task_workflow"),
                    },
                )
                self._write_state_partition(task, step, merged)

                task.execution_refs[step.step_id] = merged
                target = self.execution_planner.next_target(step, outcome)
                task = self.transition_engine.apply(task, target)

                if task.current_status in (TaskStatus.completed, TaskStatus.blocked, TaskStatus.failed):
                    break

                if task.current_step_id not in step_map:
                    task.current_status = TaskStatus.failed
                    task.result_summary = f"invalid next step: {task.current_step_id}"
                    break
            except Exception as exc:
                task.current_status = TaskStatus.failed
                task.result_summary = f"execution error at step {step.step_id}: {exc}"
                break

        if task.current_status == TaskStatus.completed:
            self._consolidate_task_memory(task)
        if task.current_status in {TaskStatus.blocked, TaskStatus.failed} and not task.result_summary:
            task.result_summary = "execution stopped; inspect task trace for details"
        return task

    def _preflight_task(self, task: Task, ir) -> dict | None:
        if self.model_router is None:
            return {
                "ok": False,
                "code": "MODEL_ROUTE_MISSING",
                "message": "model router unavailable in runtime",
            }
        routing = self.model_router.resolve(
            "step_execution",
            organization_id=task.organization_id,
        )
        if not routing:
            return {
                "ok": False,
                "code": "MODEL_ROUTE_MISSING",
                "message": "no step_execution model route configured for organization",
            }
        if not routing.get("api_key"):
            return {
                "ok": False,
                "code": "MODEL_API_KEY_MISSING",
                "message": "model route resolved without API key",
            }
        provider_type = str(routing.get("provider_type", ""))
        if provider_type in {"litellm", "openai"}:
            base_url = routing.get("base_url")
            if provider_type == "litellm" and not base_url:
                return {
                    "ok": False,
                    "code": "MODEL_PROVIDER_UNREACHABLE",
                    "message": "litellm route missing base URL",
                }
            if base_url:
                try:
                    with httpx.Client(timeout=2.0) as client:
                        probe = client.get(str(base_url))
                    if probe.status_code >= 500:
                        return {
                            "ok": False,
                            "code": "MODEL_PROVIDER_UNREACHABLE",
                            "message": f"model provider returned HTTP {probe.status_code}",
                        }
                except Exception as exc:
                    return {
                        "ok": False,
                        "code": "MODEL_PROVIDER_UNREACHABLE",
                        "message": str(exc),
                    }

        missing_connectors: list[str] = []
        for step in ir.steps:
            for capability_id in step.required_capabilities:
                if self.capability_registry is None:
                    continue
                capability = self.capability_registry.get(capability_id)
                if capability is None:
                    continue
                connector = (capability.connector_binding or "").strip()
                if not connector or connector in {"none", "verification", "review"}:
                    continue
                if not self._connector_available(connector, task.organization_id):
                    missing_connectors.append(connector)

        if missing_connectors:
            uniq = sorted(set(missing_connectors))
            return {
                "ok": False,
                "code": "CONNECTOR_UNAVAILABLE",
                "message": f"missing required connector(s): {', '.join(uniq)}",
            }
        return None

    def _connector_available(self, connector: str, organization_id: str) -> bool:
        known_commands = {"git", "gh", "node", "java", "plantuml", "opencode"}
        if connector in known_commands:
            cmd = connector
            if connector == "opencode" and self.repositories is not None:
                org = self.repositories.organization.get_or_create(organization_id)
                cmd = (org.opencode_cmd or (self.settings.opencode_cmd if self.settings else "opencode") or "opencode")
            return shutil.which(cmd) is not None

        if connector == "graphiti":
            if not self.settings or not self.settings.graphiti_enabled or not self.settings.graphiti_base_url:
                return False
            try:
                with httpx.Client(timeout=2.0) as client:
                    resp = client.get(self.settings.graphiti_base_url)
                return resp.status_code < 500
            except Exception:
                return False

        if connector in {"litellm", "openai"}:
            if self.model_router is None:
                return False
            route = self.model_router.resolve("step_execution", organization_id=organization_id)
            if not route:
                return False
            if connector == "litellm" and route.get("provider_type") != "litellm":
                return False
            if connector == "openai" and route.get("provider_type") != "openai":
                return False
            return bool(route.get("api_key"))

        return True

    def _role_policy_ids(self, role_id: str) -> list[str]:
        role_registry = getattr(self.participant_resolver, "role_registry", None)
        if role_registry is None:
            return []
        role = role_registry.get(role_id)
        if not role:
            return []
        return role.policy_ids

    def _maybe_run_subworkflow(self, task: Task, step, merged: dict) -> dict:
        if self.repositories is None:
            return merged
        hints = step.memory_hints or {}
        subworkflow_id = hints.get("subworkflow_id")
        if not subworkflow_id:
            return merged
        subworkflow_version = hints.get("subworkflow_version")
        if subworkflow_version is None:
            workflow = self.execution_planner.workflow_registry.get_active(subworkflow_id)
        else:
            workflow = self.execution_planner.workflow_registry.get_version(subworkflow_id, int(subworkflow_version))
        if workflow is None:
            raise ValueError(f"subworkflow not found: {subworkflow_id}:{subworkflow_version or 'active'}")

        child = Task(
            task_id=str(uuid4()),
            organization_id=task.organization_id,
            raw_request=f"subworkflow dispatch from {task.task_id}:{step.step_id}",
            normalized_request=f"subworkflow dispatch from {task.task_id}:{step.step_id}",
            domain_pack=task.domain_pack,
            workflow_id=subworkflow_id,
            workflow_version=workflow["version"],
            current_status=TaskStatus.workflow_selected,
            linked_entities={
                **task.linked_entities,
                "parent_task_id": task.task_id,
                "parent_step_id": step.step_id,
            },
        )
        self.repositories.tasks.create(child)
        child = self.run_task(child)
        self.repositories.tasks.update(child)
        merged["subworkflow"] = {
            "task_id": child.task_id,
            "workflow_id": child.workflow_id,
            "workflow_version": child.workflow_version,
            "status": child.current_status.value,
        }
        return merged

    def _write_state_partition(self, task: Task, step, merged: dict) -> None:
        if self.state_partition_service is None:
            return
        hints = step.memory_hints or {}
        partition_id = hints.get("state_partition")
        if not partition_id:
            return
        self.state_partition_service.write(
            partition_id=partition_id,
            key=f"{task.task_id}:{step.step_id}",
            actor_role=step.owned_by,
            payload={
                "task_id": task.task_id,
                "step_id": step.step_id,
                "workflow_id": task.workflow_id,
                "workflow_version": task.workflow_version,
                "result": merged,
            },
        )

    def _consolidate_task_memory(self, task: Task) -> None:
        if self.memory_service is None:
            return
        seen: set[tuple[tuple[str, str], ...]] = set()
        for result in task.execution_refs.values():
            scopes = (result or {}).get("memory_scopes_written") or []
            for scope in scopes:
                normalized = tuple(
                    sorted((str(k), str(v)) for k, v in scope.items() if v is not None)
                )
                if normalized in seen:
                    continue
                seen.add(normalized)
                self.memory_service.consolidate(scope)
