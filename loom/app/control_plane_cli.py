from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import httpx

from loom.app.bundle_ops import apply_bundle_spec, export_bundle_spec, load_bundle_spec
from loom.app.config import load_settings, validate_settings
from loom.app.dependency_injection import Container
from loom.models import (
    CapabilityDefinition,
    Organization,
    PolicyDefinition,
    PromptProfile,
    RoleDefinition,
    StatusEnum,
    WorkflowDefinitionMetadata,
    WorkflowMarkdownDocument,
)


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, default=str))


def _load_markdown(path: str) -> str:
    source = Path(path)
    if not source.exists():
        raise SystemExit(f"markdown file not found: {source}")
    return source.read_text(encoding="utf-8")


def _parse_capability_specs(items: list[str]) -> list[CapabilityDefinition]:
    parsed: list[CapabilityDefinition] = []
    for item in items:
        parts = item.split(":", 2)
        if len(parts) == 1:
            capability_id = parts[0].strip()
            description = capability_id
            connector = None
        elif len(parts) == 2:
            capability_id, description = parts
            connector = None
        else:
            capability_id, description, connector = parts
        capability_id = capability_id.strip()
        if not capability_id:
            raise SystemExit(f"invalid --ensure-capability value: {item}")
        parsed.append(
            CapabilityDefinition(
                capability_id=capability_id,
                description=(description or capability_id).strip(),
                connector_binding=(connector.strip() if connector else None),
                status=StatusEnum.active,
            )
        )
    return parsed


def _parse_policy_specs(items: list[str]) -> list[PolicyDefinition]:
    parsed: list[PolicyDefinition] = []
    for item in items:
        parts = item.split(":", 1)
        policy_id = parts[0].strip()
        if not policy_id:
            raise SystemExit(f"invalid --ensure-policy value: {item}")
        description = parts[1].strip() if len(parts) == 2 and parts[1].strip() else policy_id
        parsed.append(
            PolicyDefinition(
                policy_id=policy_id,
                description=description,
                scope="global",
                enforcement="block",
                rules={},
                status=StatusEnum.active,
            )
        )
    return parsed


def _default_workflow_markdown(role_id: str, capability_id: str, title: str) -> str:
    return f"""## Title
{title}
## Purpose
Execute a starter custom workflow.
## Trigger
custom_local
## Required Inputs
- topic
## Steps
1. Execute core step
- id: execute_core
- owned_by: {role_id}
- required_capabilities: {capability_id}
- on_success: completed
## Completion Criteria
Core step is completed with actionable output.
## Blocked Conditions
Missing required inputs.
## Failure Conditions
Runtime adapter failures.
## Rules
- keep outputs concise
"""


def _build_container() -> Container:
    settings = load_settings()
    validate_settings(settings)
    return Container(settings)


def _remote_base_headers(args: argparse.Namespace) -> dict[str, str]:
    if args.auth_mode == "token":
        token = args.token or os.getenv("LOOM_OPERATOR_TOKEN") or os.getenv("LOOM_ADMIN_TOKEN")
        if not token:
            raise SystemExit("token auth mode requires --token or LOOM_OPERATOR_TOKEN/LOOM_ADMIN_TOKEN")
        return {"authorization": f"Bearer {token}"}
    return {"x-loom-role": args.role}


def _remote_request(
    args: argparse.Namespace,
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_payload: dict[str, Any] | None = None,
) -> Any:
    base_headers = _remote_base_headers(args)
    timeout = float(args.timeout_seconds)
    with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=timeout) as client:
        headers = dict(base_headers)
        if method.upper() in {"POST", "PUT", "PATCH", "DELETE"} and args.auth_mode == "token":
            csrf_resp = client.get("/api/auth/csrf", headers=base_headers)
            csrf_resp.raise_for_status()
            csrf = csrf_resp.json()["csrf"]
            headers["x-csrf-token"] = csrf
        response = client.request(method, path, params=params, json=json_payload, headers=headers)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text
            raise SystemExit(f"remote request failed ({exc.response.status_code}): {body}") from exc
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            return response.json()
        return response.text


def _organization_show(container: Container, _args: argparse.Namespace) -> None:
    _print_json(container.repositories.organization.get_or_create(_args.org_id).model_dump(mode="json"))


def _organization_list(container: Container, _args: argparse.Namespace) -> None:
    _print_json([org.model_dump(mode="json") for org in container.repositories.organization.list()])


def _organization_set(container: Container, args: argparse.Namespace) -> None:
    current = container.repositories.organization.get_or_create(args.org_id)
    org = Organization(
        org_id=args.org_id,
        name=args.name if args.name is not None else current.name,
        litellm_base_url=args.litellm_base_url if args.litellm_base_url is not None else current.litellm_base_url,
        litellm_api_key=args.litellm_api_key if args.litellm_api_key is not None else current.litellm_api_key,
        litellm_default_model=(
            args.litellm_default_model if args.litellm_default_model is not None else current.litellm_default_model
        ),
        litellm_start_cmd=(
            args.litellm_start_cmd if args.litellm_start_cmd is not None else current.litellm_start_cmd
        ),
        openai_api_key=args.openai_api_key if args.openai_api_key is not None else current.openai_api_key,
        openai_model=args.openai_model if args.openai_model is not None else current.openai_model,
        opencode_enabled=(
            args.opencode_enabled if args.opencode_enabled is not None else current.opencode_enabled
        ),
        opencode_cmd=args.opencode_cmd if args.opencode_cmd is not None else current.opencode_cmd,
    )
    saved = container.repositories.organization.upsert(org)
    _print_json({"ok": True, "organization": saved.model_dump(mode="json")})


def _organization_runtime_status(container: Container, args: argparse.Namespace) -> None:
    _print_json(container.organization_runtime_service.status(args.org_id))


def _organization_runtime_run(container: Container, args: argparse.Namespace) -> None:
    _print_json(container.organization_runtime_service.run(args.org_id))


def _organization_runtime_stop(container: Container, args: argparse.Namespace) -> None:
    _print_json(container.organization_runtime_service.stop(args.org_id))


def _agent_list(container: Container, args: argparse.Namespace) -> None:
    roles = container.role_registry.list(status=args.status)
    _print_json([item.model_dump(mode="json") for item in roles])


def _agent_create(container: Container, args: argparse.Namespace) -> None:
    ensured_capabilities = _parse_capability_specs(args.ensure_capability or [])
    ensured_policies = _parse_policy_specs(args.ensure_policy or [])

    for capability in ensured_capabilities:
        container.capability_registry.upsert(capability)
    for policy in ensured_policies:
        container.policy_registry.upsert(policy)

    for capability_id in args.capability_ids:
        if not container.capability_registry.get(capability_id):
            raise SystemExit(
                f"missing capability '{capability_id}'. "
                "Provide --ensure-capability capability_id[:description[:connector_binding]]."
            )
    for policy_id in args.policy_ids:
        if not container.policy_registry.get(policy_id):
            raise SystemExit(
                f"missing policy '{policy_id}'. Provide --ensure-policy policy_id[:description]."
            )

    role = RoleDefinition(
        role_id=args.role_id,
        title=args.title,
        domain_pack=args.domain_pack,
        capability_ids=args.capability_ids,
        policy_ids=args.policy_ids,
        memory_visibility=args.memory_visibility or [],
        preferred_model_id=args.preferred_model_id,
        status=args.status,
    )
    prompt = PromptProfile(
        profile_id=args.prompt_profile_id or f"{args.role_id}_prompt",
        version=args.prompt_version,
        domain_pack=args.domain_pack,
        system_prompt=args.prompt or f"You are {args.title}.",
        status=StatusEnum.active,
    )
    container.prompt_registry.upsert(prompt)
    container.role_registry.upsert(role)
    _print_json(
        {
            "ok": True,
            "role": role.model_dump(mode="json"),
            "prompt_profile": prompt.model_dump(mode="json"),
            "ensured_capabilities": [c.capability_id for c in ensured_capabilities],
            "ensured_policies": [p.policy_id for p in ensured_policies],
        }
    )


def _workflow_list(container: Container, args: argparse.Namespace) -> None:
    rows = container.workflow_registry.list_all()
    if args.domain_pack:
        rows = [row for row in rows if (row.get("metadata") or {}).get("domain_pack") == args.domain_pack]
    _print_json(rows)


def _workflow_validate(container: Container, args: argparse.Namespace) -> None:
    markdown = _load_markdown(args.markdown_file)
    parsed = container.parser.parse(markdown)
    compiled = container.compiler.compile(args.workflow_id, args.version, parsed)
    errors = container.ir_validator.validate(compiled)
    _print_json({"ok": len(errors) == 0, "errors": errors, "compiled_ir": compiled.model_dump(mode="json")})


def _workflow_publish(container: Container, args: argparse.Namespace) -> None:
    markdown = _load_markdown(args.markdown_file)
    metadata = WorkflowDefinitionMetadata(
        workflow_id=args.workflow_id,
        version=args.version,
        title=args.title,
        domain_pack=args.domain_pack,
        intent_group=args.intent_group,
    )
    doc = WorkflowMarkdownDocument(
        workflow_id=args.workflow_id,
        version=args.version,
        markdown=markdown,
    )
    container.compiler_service.publish_from_markdown(metadata, doc, activate=args.activate)
    _print_json(
        {
            "ok": True,
            "workflow_id": args.workflow_id,
            "version": args.version,
            "activated": args.activate,
        }
    )


def _task_intake(container: Container, args: argparse.Namespace) -> None:
    tasks = _intake_tasks(
        container,
        request=args.request,
        domain_pack=args.domain_pack,
        organization_id=args.organization_id,
        workflow_id=args.workflow_id,
        workflow_version=args.workflow_version,
        fanout=args.fanout,
    )
    if args.run:
        tasks = _run_tasks(container, tasks)

    payload: dict[str, Any]
    if len(tasks) == 1:
        payload = {"task": tasks[0].model_dump(mode="json")}
    else:
        payload = {"tasks": [task.model_dump(mode="json") for task in tasks]}

    if args.trace and len(tasks) == 1:
        payload["trace"] = _trace_for_task(container, tasks[0].task_id)
    _print_json(payload)


def _task_run(container: Container, args: argparse.Namespace) -> None:
    task = container.repositories.tasks.get(args.task_id)
    if not task:
        raise SystemExit(f"task not found: {args.task_id}")
    if not task.workflow_id or task.workflow_version is None:
        raise SystemExit(f"task has no selected workflow: {args.task_id}")
    task = _run_tasks(container, [task])[0]
    payload: dict[str, Any] = {"task": task.model_dump(mode="json")}
    if args.trace:
        payload["trace"] = _trace_for_task(container, task.task_id)
    _print_json(payload)


def _task_list(container: Container, args: argparse.Namespace) -> None:
    rows = [
        task.model_dump(mode="json")
        for task in container.repositories.tasks.list(organization_id=args.organization_id)
    ]
    if args.limit and args.limit > 0:
        rows = rows[: args.limit]
    _print_json(rows)


def _task_trace(container: Container, args: argparse.Namespace) -> None:
    _print_json(_trace_for_task(container, args.task_id))


def _task_fanin(container: Container, args: argparse.Namespace) -> None:
    _print_json(container.intake_service.fanin_summary(args.fanout_group))


def _intake_tasks(
    container: Container,
    *,
    request: str,
    domain_pack: str,
    organization_id: str,
    workflow_id: str | None,
    workflow_version: int | None,
    fanout: bool,
) -> list:
    if fanout:
        return container.intake_service.intake_many(
            request,
            domain_pack=domain_pack,
            workflow_id=workflow_id,
            workflow_version=workflow_version,
            organization_id=organization_id,
        )
    if workflow_id:
        return [
            container.intake_service.intake_with_workflow(
                request,
                workflow_id=workflow_id,
                workflow_version=workflow_version,
                domain_pack=domain_pack,
                organization_id=organization_id,
            )
        ]
    return [
        container.intake_service.intake(
            request,
            domain_pack=domain_pack,
            organization_id=organization_id,
        )
    ]


def _run_tasks(container: Container, tasks: list) -> list:
    finalized = list(tasks)
    for idx, task in enumerate(finalized):
        if not task.workflow_id:
            continue
        task = container.execution_coordinator.run_task(task)
        container.repositories.tasks.update(task)
        finalized[idx] = task
    return finalized


def _trace_for_task(container: Container, task_id: str) -> dict:
    from loom.observability.audit_log_service import AuditLogService
    from loom.observability.trace_service import TraceService

    return TraceService(AuditLogService(container.repositories), container.langsmith_adapter).trace_for_task(task_id)


def _state_list(container: Container, args: argparse.Namespace) -> None:
    _print_json(container.state_partition_service.list(partition_id=args.partition_id, limit=args.limit))


def _state_get(container: Container, args: argparse.Namespace) -> None:
    data = container.state_partition_service.get(args.partition_id, args.key)
    if data is None:
        raise SystemExit(
            f"state partition entry not found: partition_id={args.partition_id} key={args.key}"
        )
    _print_json(data)


def _scaffold_starter(container: Container, args: argparse.Namespace) -> None:
    org = container.repositories.organization.get_or_create(args.organization_id)
    org.name = args.org_name
    if args.litellm_base_url is not None:
        org.litellm_base_url = args.litellm_base_url
    if args.litellm_api_key is not None:
        org.litellm_api_key = args.litellm_api_key
    if args.litellm_default_model is not None:
        org.litellm_default_model = args.litellm_default_model
    if args.openai_api_key is not None:
        org.openai_api_key = args.openai_api_key
    if args.openai_model is not None:
        org.openai_model = args.openai_model
    container.repositories.organization.upsert(org)

    capability = CapabilityDefinition(
        capability_id=args.capability_id,
        description=f"Starter capability for {args.agent_id}",
        connector_binding=args.capability_connector,
        status=StatusEnum.active,
    )
    container.capability_registry.upsert(capability)

    role = RoleDefinition(
        role_id=args.agent_id,
        title=args.agent_title,
        domain_pack=args.domain_pack,
        capability_ids=[args.capability_id],
        policy_ids=[],
        memory_visibility=[],
        status=StatusEnum.active,
    )
    prompt = PromptProfile(
        profile_id=f"{args.agent_id}_prompt",
        version=1,
        domain_pack=args.domain_pack,
        system_prompt=f"You are {args.agent_title}.",
        status=StatusEnum.active,
    )
    container.prompt_registry.upsert(prompt)
    container.role_registry.upsert(role)

    markdown = (
        _load_markdown(args.workflow_markdown_file)
        if args.workflow_markdown_file
        else _default_workflow_markdown(args.agent_id, args.capability_id, args.workflow_title)
    )
    metadata = WorkflowDefinitionMetadata(
        workflow_id=args.workflow_id,
        version=args.workflow_version,
        title=args.workflow_title,
        domain_pack=args.domain_pack,
        intent_group=args.intent_group,
    )
    doc = WorkflowMarkdownDocument(
        workflow_id=args.workflow_id,
        version=args.workflow_version,
        markdown=markdown,
    )
    container.compiler_service.publish_from_markdown(metadata, doc, activate=True)

    payload: dict[str, Any] = {
        "ok": True,
        "organization": org.model_dump(mode="json"),
        "agent_id": args.agent_id,
        "workflow_id": args.workflow_id,
        "workflow_version": args.workflow_version,
        "domain_pack": args.domain_pack,
    }
    if args.request:
        task = container.intake_service.intake_with_workflow(
            args.request,
            workflow_id=args.workflow_id,
            workflow_version=args.workflow_version,
            domain_pack=args.domain_pack,
            organization_id=args.organization_id,
        )
        if task.workflow_id:
            task = container.execution_coordinator.run_task(task)
            container.repositories.tasks.update(task)
        payload["task"] = task.model_dump(mode="json")
    _print_json(payload)


def _bundle_apply(container: Container, args: argparse.Namespace) -> None:
    try:
        spec, base_dir = load_bundle_spec(args.spec_file)
        if "organization" in spec and isinstance(spec["organization"], dict):
            spec["organization"].setdefault("org_id", args.organization_id)
        summary = apply_bundle_spec(container, spec, base_dir=base_dir)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    summary["spec_file"] = str(Path(args.spec_file))
    _print_json({"ok": True, "summary": summary})


def _bundle_export(container: Container, args: argparse.Namespace) -> None:
    spec = export_bundle_spec(
        container,
        organization_id=args.organization_id,
        domain_pack=args.domain_pack,
    )
    payload = json.dumps(spec, indent=2, default=str) if args.format == "json" else None
    if args.format == "yaml":
        import yaml

        payload = yaml.safe_dump(spec, sort_keys=False)
    assert payload is not None
    if args.output_file:
        Path(args.output_file).write_text(payload, encoding="utf-8")
        _print_json({"ok": True, "output_file": str(Path(args.output_file).resolve())})
        return
    print(payload)


def _remote_auth_check(args: argparse.Namespace) -> None:
    _print_json(_remote_request(args, "GET", "/api/auth/me"))


def _remote_organization_show(args: argparse.Namespace) -> None:
    _print_json(_remote_request(args, "GET", "/api/organization", params={"org_id": args.org_id}))


def _remote_organization_set(args: argparse.Namespace) -> None:
    payload: dict[str, Any] = {"org_id": args.org_id, "name": args.name}
    for field in (
        "litellm_base_url",
        "litellm_api_key",
        "litellm_default_model",
        "litellm_start_cmd",
        "openai_api_key",
        "openai_model",
        "opencode_cmd",
    ):
        value = getattr(args, field)
        if value is not None:
            payload[field] = value
    if args.opencode_enabled is not None:
        payload["opencode_enabled"] = args.opencode_enabled
    _print_json(_remote_request(args, "POST", "/api/organization", json_payload=payload))


def _remote_organization_runtime_status(args: argparse.Namespace) -> None:
    _print_json(_remote_request(args, "GET", "/api/organization/runtime", params={"org_id": args.org_id}))


def _remote_organization_runtime_run(args: argparse.Namespace) -> None:
    _print_json(
        _remote_request(
            args,
            "POST",
            "/api/organization/runtime/run",
            json_payload={"org_id": args.org_id},
        )
    )


def _remote_organization_runtime_stop(args: argparse.Namespace) -> None:
    _print_json(
        _remote_request(
            args,
            "POST",
            "/api/organization/runtime/stop",
            json_payload={"org_id": args.org_id},
        )
    )


def _remote_workflow_list(args: argparse.Namespace) -> None:
    rows = _remote_request(args, "GET", "/api/workflows")
    if args.domain_pack:
        rows = [row for row in rows if (row.get("metadata") or {}).get("domain_pack") == args.domain_pack]
    _print_json(rows)


def _remote_task_intake(args: argparse.Namespace) -> None:
    payload: dict[str, Any] = {
        "request": args.request,
        "domain_pack": args.domain_pack,
        "organization_id": args.organization_id,
        "async_run": args.async_run,
        "workflow_id": args.workflow_id,
        "workflow_version": args.workflow_version,
        "fanout": args.fanout,
    }
    _print_json(_remote_request(args, "POST", "/api/tasks/intake", json_payload=payload))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Loom control plane CLI")
    subparsers = parser.add_subparsers(dest="resource", required=True)

    org_parser = subparsers.add_parser("organization", aliases=["org"], help="Manage organization settings")
    org_sub = org_parser.add_subparsers(dest="action", required=True)
    org_list = org_sub.add_parser("list", help="List organizations")
    org_list.set_defaults(handler=_organization_list)

    org_show = org_sub.add_parser("show", help="Show organization settings")
    org_show.add_argument("--org-id", default="default")
    org_show.set_defaults(handler=_organization_show)

    org_set = org_sub.add_parser("set", help="Update organization settings")
    org_set.add_argument("--org-id", default="default")
    org_set.add_argument("--name")
    org_set.add_argument("--litellm-base-url")
    org_set.add_argument("--litellm-api-key")
    org_set.add_argument("--litellm-default-model")
    org_set.add_argument("--litellm-start-cmd")
    org_set.add_argument("--openai-api-key")
    org_set.add_argument("--openai-model")
    org_set.add_argument("--opencode-cmd")
    org_set.add_argument("--opencode-enabled", action=argparse.BooleanOptionalAction, default=None)
    org_set.set_defaults(handler=_organization_set)

    org_runtime_status = org_sub.add_parser("runtime-status", help="Get organization runtime status")
    org_runtime_status.add_argument("--org-id", default="default")
    org_runtime_status.set_defaults(handler=_organization_runtime_status)

    org_run = org_sub.add_parser("run", help="Run organization and boot required services")
    org_run.add_argument("--org-id", default="default")
    org_run.set_defaults(handler=_organization_runtime_run)

    org_stop = org_sub.add_parser("stop", help="Stop managed services for an organization")
    org_stop.add_argument("--org-id", default="default")
    org_stop.set_defaults(handler=_organization_runtime_stop)

    agent_parser = subparsers.add_parser("agent", aliases=["agents"], help="Manage agents (roles)")
    agent_sub = agent_parser.add_subparsers(dest="action", required=True)
    agent_list = agent_sub.add_parser("list", help="List agents")
    agent_list.add_argument("--status", default=None)
    agent_list.set_defaults(handler=_agent_list)

    agent_create = agent_sub.add_parser("create", help="Create or update an agent")
    agent_create.add_argument("--role-id", required=True)
    agent_create.add_argument("--title", required=True)
    agent_create.add_argument("--domain-pack", default="custom")
    agent_create.add_argument("--preferred-model-id")
    agent_create.add_argument("--capability-ids", nargs="*", default=[])
    agent_create.add_argument("--policy-ids", nargs="*", default=[])
    agent_create.add_argument("--memory-visibility", nargs="*", default=[])
    agent_create.add_argument("--status", choices=[e.value for e in StatusEnum], default=StatusEnum.active.value)
    agent_create.add_argument("--prompt")
    agent_create.add_argument("--prompt-profile-id")
    agent_create.add_argument("--prompt-version", type=int, default=1)
    agent_create.add_argument(
        "--ensure-capability",
        action="append",
        default=[],
        help="capability_id[:description[:connector_binding]]",
    )
    agent_create.add_argument(
        "--ensure-policy",
        action="append",
        default=[],
        help="policy_id[:description]",
    )
    agent_create.set_defaults(handler=_agent_create)

    workflow_parser = subparsers.add_parser("workflow", aliases=["workflows"], help="Manage workflows")
    workflow_sub = workflow_parser.add_subparsers(dest="action", required=True)
    workflow_list = workflow_sub.add_parser("list", help="List workflows")
    workflow_list.add_argument("--domain-pack")
    workflow_list.set_defaults(handler=_workflow_list)

    workflow_validate = workflow_sub.add_parser("validate", help="Validate workflow markdown")
    workflow_validate.add_argument("--workflow-id", required=True)
    workflow_validate.add_argument("--version", type=int, required=True)
    workflow_validate.add_argument("--markdown-file", required=True)
    workflow_validate.set_defaults(handler=_workflow_validate)

    workflow_publish = workflow_sub.add_parser("publish", help="Publish workflow markdown")
    workflow_publish.add_argument("--workflow-id", required=True)
    workflow_publish.add_argument("--version", type=int, required=True)
    workflow_publish.add_argument("--title", required=True)
    workflow_publish.add_argument("--domain-pack", default="custom")
    workflow_publish.add_argument("--intent-group", required=True)
    workflow_publish.add_argument("--markdown-file", required=True)
    workflow_publish.add_argument("--activate", action=argparse.BooleanOptionalAction, default=True)
    workflow_publish.set_defaults(handler=_workflow_publish)

    task_parser = subparsers.add_parser("task", aliases=["tasks"], help="Manage tasks")
    task_sub = task_parser.add_subparsers(dest="action", required=True)

    task_intake = task_sub.add_parser("intake", help="Create task from natural-language request")
    task_intake.add_argument("--request", required=True)
    task_intake.add_argument("--domain-pack", default="docs")
    task_intake.add_argument("--organization-id", default="default")
    task_intake.add_argument("--workflow-id")
    task_intake.add_argument("--workflow-version", type=int)
    task_intake.add_argument("--fanout", action=argparse.BooleanOptionalAction, default=False)
    task_intake.add_argument("--run", action=argparse.BooleanOptionalAction, default=False)
    task_intake.add_argument("--trace", action=argparse.BooleanOptionalAction, default=False)
    task_intake.set_defaults(handler=_task_intake)

    task_run = task_sub.add_parser("run", help="Run an existing task")
    task_run.add_argument("--task-id", required=True)
    task_run.add_argument("--trace", action=argparse.BooleanOptionalAction, default=False)
    task_run.set_defaults(handler=_task_run)

    task_list = task_sub.add_parser("list", help="List tasks")
    task_list.add_argument("--organization-id")
    task_list.add_argument("--limit", type=int, default=20)
    task_list.set_defaults(handler=_task_list)

    task_trace = task_sub.add_parser("trace", help="Get task trace")
    task_trace.add_argument("--task-id", required=True)
    task_trace.set_defaults(handler=_task_trace)

    task_fanin = task_sub.add_parser("fanin", help="Summarize fan-out task group")
    task_fanin.add_argument("--fanout-group", required=True)
    task_fanin.set_defaults(handler=_task_fanin)

    scaffold_parser = subparsers.add_parser("scaffold", help="Create ready-to-run starter setup")
    scaffold_sub = scaffold_parser.add_subparsers(dest="action", required=True)
    starter = scaffold_sub.add_parser("starter", help="Scaffold organization + agent + workflow")
    starter.add_argument("--organization-id", default="default")
    starter.add_argument("--org-name", default="My Organization")
    starter.add_argument("--domain-pack", default="custom")
    starter.add_argument("--agent-id", default="custom_agent")
    starter.add_argument("--agent-title", default="Custom Agent")
    starter.add_argument("--capability-id", default="custom_capability")
    starter.add_argument("--capability-connector", default="none")
    starter.add_argument("--workflow-id", default="custom_workflow")
    starter.add_argument("--workflow-version", type=int, default=1)
    starter.add_argument("--workflow-title", default="Custom Workflow")
    starter.add_argument("--intent-group", default="custom_local")
    starter.add_argument("--workflow-markdown-file")
    starter.add_argument("--request")
    starter.add_argument("--litellm-base-url")
    starter.add_argument("--litellm-api-key")
    starter.add_argument("--litellm-default-model")
    starter.add_argument("--openai-api-key")
    starter.add_argument("--openai-model")
    starter.set_defaults(handler=_scaffold_starter)

    bundle_parser = subparsers.add_parser("bundle", help="Apply declarative control-plane spec")
    bundle_sub = bundle_parser.add_subparsers(dest="action", required=True)
    bundle_apply = bundle_sub.add_parser("apply", help="Apply YAML spec idempotently")
    bundle_apply.add_argument("--spec-file", required=True)
    bundle_apply.add_argument("--organization-id", default="default")
    bundle_apply.set_defaults(handler=_bundle_apply)
    bundle_export = bundle_sub.add_parser("export", help="Export current control-plane config as bundle")
    bundle_export.add_argument("--organization-id", default="default")
    bundle_export.add_argument("--domain-pack")
    bundle_export.add_argument("--format", choices=["yaml", "json"], default="yaml")
    bundle_export.add_argument("--output-file")
    bundle_export.set_defaults(handler=_bundle_export)

    state_parser = subparsers.add_parser("state", aliases=["states"], help="Inspect state partitions")
    state_sub = state_parser.add_subparsers(dest="action", required=True)
    state_list = state_sub.add_parser("list", help="List state partition entries")
    state_list.add_argument("--partition-id")
    state_list.add_argument("--limit", type=int, default=200)
    state_list.set_defaults(handler=_state_list)

    state_get = state_sub.add_parser("get", help="Get one state partition entry")
    state_get.add_argument("--partition-id", required=True)
    state_get.add_argument("--key", required=True)
    state_get.set_defaults(handler=_state_get)

    remote_parser = subparsers.add_parser("remote", help="Call remote HTTP control plane with explicit auth mode")
    remote_parser.add_argument("--base-url", required=True, help="Base URL, e.g. http://127.0.0.1:8000")
    remote_parser.add_argument("--auth-mode", choices=["token", "header"], default="token")
    remote_parser.add_argument("--token", help="Bearer token for token auth mode")
    remote_parser.add_argument("--role", default="operator", help="Role header for header auth mode")
    remote_parser.add_argument("--timeout-seconds", type=float, default=30.0)
    remote_sub = remote_parser.add_subparsers(dest="remote_resource", required=True)

    remote_auth = remote_sub.add_parser("auth-check", help="Validate remote auth context")
    remote_auth.set_defaults(handler=_remote_auth_check)

    remote_org = remote_sub.add_parser("organization", aliases=["org"], help="Remote organization operations")
    remote_org_sub = remote_org.add_subparsers(dest="remote_action", required=True)
    remote_org_show = remote_org_sub.add_parser("show")
    remote_org_show.add_argument("--org-id", default="default")
    remote_org_show.set_defaults(handler=_remote_organization_show)
    remote_org_set = remote_org_sub.add_parser("set")
    remote_org_set.add_argument("--org-id", default="default")
    remote_org_set.add_argument("--name", required=True)
    remote_org_set.add_argument("--litellm-base-url")
    remote_org_set.add_argument("--litellm-api-key")
    remote_org_set.add_argument("--litellm-default-model")
    remote_org_set.add_argument("--litellm-start-cmd")
    remote_org_set.add_argument("--openai-api-key")
    remote_org_set.add_argument("--openai-model")
    remote_org_set.add_argument("--opencode-cmd")
    remote_org_set.add_argument("--opencode-enabled", action=argparse.BooleanOptionalAction, default=None)
    remote_org_set.set_defaults(handler=_remote_organization_set)

    remote_org_runtime_status = remote_org_sub.add_parser("runtime-status")
    remote_org_runtime_status.add_argument("--org-id", default="default")
    remote_org_runtime_status.set_defaults(handler=_remote_organization_runtime_status)

    remote_org_run = remote_org_sub.add_parser("run")
    remote_org_run.add_argument("--org-id", default="default")
    remote_org_run.set_defaults(handler=_remote_organization_runtime_run)

    remote_org_stop = remote_org_sub.add_parser("stop")
    remote_org_stop.add_argument("--org-id", default="default")
    remote_org_stop.set_defaults(handler=_remote_organization_runtime_stop)

    remote_workflow = remote_sub.add_parser("workflow", aliases=["workflows"], help="Remote workflow operations")
    remote_workflow_sub = remote_workflow.add_subparsers(dest="remote_action", required=True)
    remote_workflow_list = remote_workflow_sub.add_parser("list")
    remote_workflow_list.add_argument("--domain-pack")
    remote_workflow_list.set_defaults(handler=_remote_workflow_list)

    remote_task = remote_sub.add_parser("task", aliases=["tasks"], help="Remote task operations")
    remote_task_sub = remote_task.add_subparsers(dest="remote_action", required=True)
    remote_task_intake = remote_task_sub.add_parser("intake")
    remote_task_intake.add_argument("--request", required=True)
    remote_task_intake.add_argument("--domain-pack", default="docs")
    remote_task_intake.add_argument("--organization-id", default="default")
    remote_task_intake.add_argument("--workflow-id")
    remote_task_intake.add_argument("--workflow-version", type=int)
    remote_task_intake.add_argument("--fanout", action=argparse.BooleanOptionalAction, default=False)
    remote_task_intake.add_argument("--async-run", action=argparse.BooleanOptionalAction, default=False)
    remote_task_intake.set_defaults(handler=_remote_task_intake)

    return parser


def run_control_plane_cli(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.resource == "remote":
        args.handler(args)
        return
    container = _build_container()
    args.handler(container, args)
