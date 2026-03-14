from __future__ import annotations

import json
import shlex
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from loom.app.bundle_ops import apply_bundle_spec, export_bundle_spec, load_bundle_spec
from loom.integrations.health import connector_health
from loom.models import (
    CapabilityDefinition,
    MemoryGroupDefinition,
    MemoryGroupMembership,
    ModelDefinition,
    ModelProviderDefinition,
    Organization,
    PromptProfile,
    RoleDefinition,
    ServiceModelBinding,
    WorkflowDefinitionMetadata,
    WorkflowMarkdownDocument,
)
from loom.observability.audit_log_service import AuditLogService
from loom.observability.trace_service import TraceService


def _parse_kv_options(items: list[str]) -> dict[str, str]:
    options: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        options[key.strip()] = value.strip()
    return options


def _json(payload: Any) -> str:
    return json.dumps(payload, indent=2, default=str)


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"invalid boolean value: {value}")


def _workflow_diff(markdown_a: str, markdown_b: str) -> dict[str, list[str]]:
    a_lines = markdown_a.splitlines()
    b_lines = markdown_b.splitlines()
    removed = [line for line in a_lines if line not in b_lines]
    added = [line for line in b_lines if line not in a_lines]
    return {"added": added[:200], "removed": removed[:200]}


@dataclass
class SessionState:
    selected_org_id: str = "default"
    selected_agent_id: str | None = None
    selected_workflow_id: str | None = None
    selected_workflow_version: int | None = None
    selected_domain_pack: str = "docs"


class LoomChatSession:
    def __init__(self, container):
        self.container = container
        self.state = SessionState()

    def handle_line(self, line: str) -> dict[str, Any]:
        text = line.strip()
        if not text:
            return {"kind": "noop", "message": ""}
        if text.startswith("/"):
            return self._handle_command(text)
        return self._handle_chat_message(text)

    def _trace_for_task(self, task_id: str) -> dict[str, Any]:
        return TraceService(
            AuditLogService(self.container.repositories), self.container.langsmith_adapter
        ).trace_for_task(task_id)

    def _intake_tasks(
        self,
        *,
        request: str,
        domain_pack: str,
        organization_id: str,
        workflow_id: str | None,
        workflow_version: int | None,
        fanout: bool,
    ) -> list:
        if fanout:
            return self.container.intake_service.intake_many(
                request,
                domain_pack=domain_pack,
                workflow_id=workflow_id,
                workflow_version=workflow_version,
                organization_id=organization_id,
            )
        if workflow_id:
            return [
                self.container.intake_service.intake_with_workflow(
                    request,
                    workflow_id=workflow_id,
                    workflow_version=workflow_version,
                    domain_pack=domain_pack,
                    organization_id=organization_id,
                )
            ]
        return [
            self.container.intake_service.intake(
                request,
                domain_pack=domain_pack,
                organization_id=organization_id,
            )
        ]

    def _run_tasks(self, tasks: list) -> list:
        finalized = list(tasks)
        for idx, task in enumerate(finalized):
            if not task.workflow_id:
                continue
            task = self.container.execution_coordinator.run_task(task)
            self.container.repositories.tasks.update(task)
            finalized[idx] = task
        return finalized

    def _handle_command(self, command_line: str) -> dict[str, Any]:
        tokens = shlex.split(command_line)
        command = tokens[0].lower()
        args = tokens[1:]

        if command in {"/help", "/?"}:
            return {"kind": "help", "message": self._help_text()}
        if command == "/status":
            return {"kind": "status", "state": self.state.__dict__}
        if command in {"/exit", "/quit"}:
            return {"kind": "exit", "message": "Bye."}
        if command == "/organization":
            return self._command_organization(args)
        if command == "/agents":
            return self._command_agents(args)
        if command == "/workflows":
            return self._command_workflows(args)
        if command == "/domain":
            return self._command_domain(args)
        if command == "/models":
            return self._command_models(args)
        if command == "/bundle":
            return self._command_bundle(args)
        if command == "/integrations":
            return self._command_integrations(args)
        if command == "/tasks":
            return self._command_tasks(args)
        if command == "/memory":
            return self._command_memory(args)
        if command == "/artifacts":
            return self._command_artifacts(args)
        if command == "/state":
            return self._command_state(args)

        return {"kind": "error", "message": f"Unknown command: {command}. Try /help"}

    def _command_domain(self, args: list[str]) -> dict[str, Any]:
        if not args:
            return {"kind": "domain", "domain_pack": self.state.selected_domain_pack}
        self.state.selected_domain_pack = args[0]
        return {"kind": "domain", "domain_pack": self.state.selected_domain_pack}

    def _apply_org_overrides(self, org: Organization, opts: dict[str, str]) -> Organization:
        if "name" in opts:
            org.name = opts["name"]
        if "litellm_base_url" in opts:
            org.litellm_base_url = opts["litellm_base_url"]
        if "litellm_api_key" in opts:
            org.litellm_api_key = opts["litellm_api_key"]
        if "litellm_default_model" in opts:
            org.litellm_default_model = opts["litellm_default_model"]
        if "litellm_start_cmd" in opts:
            org.litellm_start_cmd = opts["litellm_start_cmd"]
        if "openai_api_key" in opts:
            org.openai_api_key = opts["openai_api_key"]
        if "openai_model" in opts:
            org.openai_model = opts["openai_model"]
        if "opencode_enabled" in opts:
            org.opencode_enabled = opts["opencode_enabled"].lower() == "true"
        if "opencode_cmd" in opts:
            org.opencode_cmd = opts["opencode_cmd"]
        return org

    def _command_organization(self, args: list[str]) -> dict[str, Any]:
        if not args or args[0] in {"view", "show"}:
            org_id = args[1] if len(args) > 1 else self.state.selected_org_id
            org = self.container.repositories.organization.get_or_create(org_id)
            self.state.selected_org_id = org.org_id
            return {
                "kind": "organization",
                "selected_org_id": self.state.selected_org_id,
                "organization": org.model_dump(mode="json"),
            }

        action = args[0]
        if action == "list":
            items = [org.model_dump(mode="json") for org in self.container.repositories.organization.list()]
            return {"kind": "organization_list", "selected_org_id": self.state.selected_org_id, "items": items}

        if action == "select":
            if len(args) < 2 or "=" in args[1]:
                return {"kind": "error", "message": "Usage: /organization select <org_id>"}
            org = self.container.repositories.organization.get(args[1])
            if not org:
                return {"kind": "error", "message": f"organization not found: {args[1]}"}
            self.state.selected_org_id = org.org_id
            return {"kind": "organization", "message": f"Selected organization: {org.org_id}"}

        if action in {"run", "runtime", "status", "stop"}:
            org_id = args[1] if len(args) > 1 and "=" not in args[1] else self.state.selected_org_id
            self.state.selected_org_id = org_id
            if action == "run":
                runtime = self.container.organization_runtime_service.run(org_id)
            elif action == "stop":
                runtime = self.container.organization_runtime_service.stop(org_id)
            else:
                runtime = self.container.organization_runtime_service.status(org_id)
            return {"kind": "organization_runtime", "organization_id": org_id, "runtime": runtime}

        if action in {"create", "update"}:
            org_id = self.state.selected_org_id
            name_arg: str | None = None
            start = 1
            if action == "create":
                if len(args) < 2 or "=" in args[1]:
                    return {
                        "kind": "error",
                        "message": "Usage: /organization create <org_id> [name] [k=v...]",
                    }
                org_id = args[1]
                start = 2
                if len(args) > 2 and "=" not in args[2]:
                    name_arg = args[2]
                    start = 3
            else:
                if len(args) > 1 and "=" not in args[1]:
                    candidate = self.container.repositories.organization.get(args[1])
                    if candidate:
                        org_id = candidate.org_id
                        start = 2
                        if len(args) > 2 and "=" not in args[2]:
                            name_arg = args[2]
                            start = 3
                    else:
                        name_arg = args[1]
                        start = 2

            opts = _parse_kv_options(args[start:])
            if "org_id" in opts:
                org_id = opts["org_id"]
            org = self.container.repositories.organization.get_or_create(org_id)
            if name_arg:
                org.name = name_arg
            org = self._apply_org_overrides(org, opts)
            saved = self.container.repositories.organization.upsert(org)
            self.state.selected_org_id = saved.org_id
            return {
                "kind": "organization",
                "selected_org_id": self.state.selected_org_id,
                "organization": saved.model_dump(mode="json"),
            }

        return {
            "kind": "error",
            "message": "Usage: /organization [list|view|select|create|update|run|runtime|status|stop] ...",
        }

    def _command_agents(self, args: list[str]) -> dict[str, Any]:
        if not args or args[0] == "list":
            roles = [r.model_dump(mode="json") for r in self.container.role_registry.list()]
            return {"kind": "agents", "items": roles}

        action = args[0]
        if action == "select":
            if len(args) < 2:
                return {"kind": "error", "message": "Usage: /agents select <role_id>"}
            role = self.container.role_registry.get(args[1])
            if not role:
                return {"kind": "error", "message": f"role not found: {args[1]}"}
            self.state.selected_agent_id = role.role_id
            return {"kind": "agents", "selected_agent_id": role.role_id}

        if action == "create":
            if len(args) < 3:
                return {
                    "kind": "error",
                    "message": (
                        "Usage: /agents create <role_id> \"Title\" "
                        "[domain_pack=docs] [capabilities=cap1,cap2] [connector=none] [model_id=<model_id>]"
                    ),
                }
            role_id = args[1]
            title = args[2]
            opts = _parse_kv_options(args[3:])
            domain_pack = opts.get("domain_pack", self.state.selected_domain_pack)
            capabilities_csv = opts.get("capabilities", "")
            capability_ids = [c.strip() for c in capabilities_csv.split(",") if c.strip()]
            connector = opts.get("connector")
            preferred_model_id = opts.get("model_id") or opts.get("preferred_model_id")
            if preferred_model_id and self.container.model_registry.get(preferred_model_id) is None:
                return {"kind": "error", "message": f"model not found: {preferred_model_id}"}

            for cap_id in capability_ids:
                if self.container.capability_registry.get(cap_id):
                    continue
                self.container.capability_registry.upsert(
                    CapabilityDefinition(
                        capability_id=cap_id,
                        description=f"Auto-created capability {cap_id}",
                        connector_binding=connector or "none",
                        status="active",
                    )
                )

            role = RoleDefinition(
                role_id=role_id,
                title=title,
                domain_pack=domain_pack,
                capability_ids=capability_ids,
                policy_ids=[],
                memory_visibility=[domain_pack],
                preferred_model_id=preferred_model_id,
                status="active",
            )
            prompt = PromptProfile(
                profile_id=f"{role_id}_prompt",
                version=1,
                domain_pack=domain_pack,
                system_prompt=f"You are {title}. Follow workflow rules strictly.",
                status="active",
            )
            self.container.prompt_registry.upsert(prompt)
            self.container.role_registry.upsert(role)
            self.state.selected_agent_id = role_id
            return {
                "kind": "agents",
                "created": role.model_dump(mode="json"),
                "prompt_profile_id": prompt.profile_id,
            }

        return {"kind": "error", "message": "Usage: /agents [list|select|create] ..."}

    def _command_workflows(self, args: list[str]) -> dict[str, Any]:
        if not args or args[0] == "list":
            rows = self.container.workflow_registry.list_all()
            return {"kind": "workflows", "items": rows}

        action = args[0]
        if action == "select":
            if len(args) < 2:
                return {"kind": "error", "message": "Usage: /workflows select <workflow_id> [version]"}
            workflow_id = args[1]
            version = int(args[2]) if len(args) > 2 else None
            workflow = (
                self.container.workflow_registry.get_version(workflow_id, version)
                if version is not None
                else self.container.workflow_registry.get_active(workflow_id)
            )
            if not workflow:
                return {"kind": "error", "message": f"workflow not found: {workflow_id}"}
            self.state.selected_workflow_id = workflow_id
            self.state.selected_workflow_version = int(workflow["version"])
            metadata = workflow.get("metadata") or {}
            if metadata.get("domain_pack"):
                self.state.selected_domain_pack = metadata["domain_pack"]
            return {
                "kind": "workflows",
                "selected_workflow_id": self.state.selected_workflow_id,
                "selected_workflow_version": self.state.selected_workflow_version,
            }

        if action == "create":
            if len(args) < 3:
                return {
                    "kind": "error",
                    "message": (
                        "Usage: /workflows create <workflow_id> \"Title\" "
                        "[owned_by=<role_id>] [domain_pack=docs] [intent_group=custom_local] "
                        "[required_capabilities=cap1,cap2]"
                    ),
                }
            workflow_id = args[1]
            title = args[2]
            opts = _parse_kv_options(args[3:])
            domain_pack = opts.get("domain_pack", self.state.selected_domain_pack)
            intent_group = opts.get("intent_group", "custom_local")
            owned_by = opts.get("owned_by", self.state.selected_agent_id or "docs_ops")
            required_caps = opts.get("required_capabilities", "")
            req_caps = [c.strip() for c in required_caps.split(",") if c.strip()]
            if self.container.role_registry.get(owned_by) is None:
                return {"kind": "error", "message": f"role not found for owned_by: {owned_by}"}

            versions = self.container.workflow_registry.list_versions(workflow_id)
            version = 1 if not versions else max(v["version"] for v in versions) + 1
            caps_line = ",".join(req_caps)
            markdown = (
                f"## Title\n{title}\n"
                "## Purpose\nWorkflow created from Loom chat CLI.\n"
                "## Trigger\ncustom_local\n"
                "## Required Inputs\n- request\n"
                "## Steps\n"
                "1. Execute task\n"
                "- id: execute\n"
                f"- owned_by: {owned_by}\n"
                f"- required_capabilities: {caps_line}\n"
                "- on_success: completed\n"
                "## Completion Criteria\ndone\n"
                "## Blocked Conditions\nmissing context\n"
                "## Failure Conditions\nexecution error\n"
                "## Rules\n- follow workflow\n"
            )
            metadata = WorkflowDefinitionMetadata(
                workflow_id=workflow_id,
                version=version,
                title=title,
                domain_pack=domain_pack,
                intent_group=intent_group,
            )
            doc = WorkflowMarkdownDocument(workflow_id=workflow_id, version=version, markdown=markdown)
            self.container.compiler_service.publish_from_markdown(metadata, doc, activate=True)
            self.state.selected_workflow_id = workflow_id
            self.state.selected_workflow_version = version
            self.state.selected_domain_pack = domain_pack
            return {
                "kind": "workflows",
                "created": {"workflow_id": workflow_id, "version": version, "domain_pack": domain_pack},
            }

        if action == "versions":
            if len(args) < 2:
                return {"kind": "error", "message": "Usage: /workflows versions <workflow_id>"}
            return {
                "kind": "workflows",
                "versions": self.container.workflow_registry.list_versions(args[1]),
            }

        if action == "diff":
            if len(args) < 4:
                return {"kind": "error", "message": "Usage: /workflows diff <workflow_id> <from_version> <to_version>"}
            workflow_id = args[1]
            try:
                from_version = int(args[2])
                to_version = int(args[3])
            except ValueError:
                return {"kind": "error", "message": "workflow versions must be integers"}
            from_w = self.container.workflow_registry.get_version(workflow_id, from_version)
            to_w = self.container.workflow_registry.get_version(workflow_id, to_version)
            if not from_w or not to_w:
                return {"kind": "error", "message": "workflow version not found"}
            return {
                "kind": "workflows",
                "workflow_id": workflow_id,
                "from_version": from_version,
                "to_version": to_version,
                "diff": _workflow_diff(from_w["markdown"], to_w["markdown"]),
            }

        if action == "validate-file":
            if len(args) < 4:
                return {"kind": "error", "message": "Usage: /workflows validate-file <workflow_id> <version> <markdown_file>"}
            workflow_id = args[1]
            try:
                version = int(args[2])
            except ValueError:
                return {"kind": "error", "message": "version must be an integer"}
            source = Path(args[3])
            if not source.exists():
                return {"kind": "error", "message": f"markdown file not found: {source}"}
            markdown = source.read_text(encoding="utf-8")
            parsed = self.container.parser.parse(markdown)
            compiled = self.container.compiler.compile(workflow_id, version, parsed)
            errors = self.container.ir_validator.validate(compiled)
            return {
                "kind": "workflows",
                "validation": {
                    "ok": len(errors) == 0,
                    "errors": errors,
                    "compiled_ir": compiled.model_dump(mode="json"),
                },
            }

        if action == "publish-file":
            if len(args) < 6:
                return {
                    "kind": "error",
                    "message": (
                        "Usage: /workflows publish-file <workflow_id> <version> \"Title\" "
                        "<intent_group> <markdown_file> [domain_pack=<domain>] [activate=true|false]"
                    ),
                }
            workflow_id = args[1]
            try:
                version = int(args[2])
            except ValueError:
                return {"kind": "error", "message": "version must be an integer"}
            title = args[3]
            intent_group = args[4]
            markdown_file = Path(args[5])
            opts = _parse_kv_options(args[6:])
            if not markdown_file.exists():
                return {"kind": "error", "message": f"markdown file not found: {markdown_file}"}
            domain_pack = opts.get("domain_pack", self.state.selected_domain_pack)
            try:
                activate = _parse_bool(opts.get("activate"), default=True)
            except ValueError as exc:
                return {"kind": "error", "message": str(exc)}
            metadata = WorkflowDefinitionMetadata(
                workflow_id=workflow_id,
                version=version,
                title=title,
                domain_pack=domain_pack,
                intent_group=intent_group,
            )
            doc = WorkflowMarkdownDocument(
                workflow_id=workflow_id,
                version=version,
                markdown=markdown_file.read_text(encoding="utf-8"),
            )
            try:
                self.container.compiler_service.publish_from_markdown(metadata, doc, activate=activate)
            except ValueError as exc:
                return {"kind": "error", "message": str(exc)}
            self.state.selected_workflow_id = workflow_id
            self.state.selected_workflow_version = version
            self.state.selected_domain_pack = domain_pack
            return {
                "kind": "workflows",
                "published": {
                    "workflow_id": workflow_id,
                    "version": version,
                    "domain_pack": domain_pack,
                    "activate": activate,
                },
            }

        return {
            "kind": "error",
            "message": "Usage: /workflows [list|select|create|versions|diff|validate-file|publish-file] ...",
        }

    def _command_models(self, args: list[str]) -> dict[str, Any]:
        if not args or args[0] == "list":
            return {
                "kind": "models",
                "providers": [item.model_dump(mode="json") for item in self.container.model_provider_registry.list()],
                "models": [item.model_dump(mode="json") for item in self.container.model_registry.list()],
                "bindings": [item.model_dump(mode="json") for item in self.container.service_model_registry.list()],
            }
        action = args[0]
        if action == "providers":
            return {
                "kind": "models",
                "providers": [item.model_dump(mode="json") for item in self.container.model_provider_registry.list()],
            }
        if action == "bindings":
            return {
                "kind": "models",
                "bindings": [item.model_dump(mode="json") for item in self.container.service_model_registry.list()],
            }
        if action == "add-provider":
            if len(args) < 4:
                return {
                    "kind": "error",
                    "message": (
                        "Usage: /models add-provider <provider_id> <base_url> <api_key> "
                        "[provider_type=litellm] [status=active] [headers_json='{\"k\":\"v\"}']"
                    ),
                }
            provider_id = args[1]
            base_url = args[2]
            api_key = args[3]
            opts = _parse_kv_options(args[4:])
            headers_json = opts.get("headers_json")
            extra_headers: dict[str, str] = {}
            if headers_json:
                try:
                    parsed = json.loads(headers_json)
                except json.JSONDecodeError as exc:
                    return {"kind": "error", "message": f"invalid headers_json: {exc}"}
                if not isinstance(parsed, dict):
                    return {"kind": "error", "message": "headers_json must decode to an object"}
                extra_headers = {str(k): str(v) for k, v in parsed.items()}
            provider = ModelProviderDefinition(
                provider_id=provider_id,
                provider_type=opts.get("provider_type", "litellm"),
                base_url=base_url,
                api_key=api_key,
                extra_headers=extra_headers,
                status=opts.get("status", "active"),
            )
            self.container.model_provider_registry.upsert(provider)
            return {"kind": "models", "provider": provider.model_dump(mode="json")}
        if action == "add-model":
            if len(args) < 4:
                return {
                    "kind": "error",
                    "message": (
                        "Usage: /models add-model <model_id> <provider_id> <model_name> "
                        "[max_tokens=<int>] [temperature=<float>] [status=active]"
                    ),
                }
            model_id = args[1]
            provider_id = args[2]
            model_name = args[3]
            opts = _parse_kv_options(args[4:])
            if self.container.model_provider_registry.get(provider_id) is None:
                return {"kind": "error", "message": f"provider not found: {provider_id}"}
            max_tokens = None
            if "max_tokens" in opts:
                try:
                    max_tokens = int(opts["max_tokens"])
                except ValueError:
                    return {"kind": "error", "message": "max_tokens must be an integer"}
            temperature = None
            if "temperature" in opts:
                try:
                    temperature = float(opts["temperature"])
                except ValueError:
                    return {"kind": "error", "message": "temperature must be a number"}
            model = ModelDefinition(
                model_id=model_id,
                provider_id=provider_id,
                model_name=model_name,
                max_tokens=max_tokens,
                temperature=temperature,
                status=opts.get("status", "active"),
            )
            self.container.model_registry.upsert(model)
            return {"kind": "models", "model": model.model_dump(mode="json")}
        if action == "bind":
            if len(args) < 3:
                return {"kind": "error", "message": "Usage: /models bind <service_id> <model_id> [status=active]"}
            service_id = args[1]
            model_id = args[2]
            opts = _parse_kv_options(args[3:])
            if self.container.model_registry.get(model_id) is None:
                return {"kind": "error", "message": f"model not found: {model_id}"}
            binding = ServiceModelBinding(service_id=service_id, model_id=model_id, status=opts.get("status", "active"))
            self.container.service_model_registry.upsert(binding)
            return {"kind": "models", "binding": binding.model_dump(mode="json")}
        if action == "resolve":
            if len(args) < 2:
                return {"kind": "error", "message": "Usage: /models resolve <service_id> [org_id=<id>] [role_id=<role_id>]"}
            service_id = args[1]
            opts = _parse_kv_options(args[2:])
            resolved = self.container.model_router.resolve_public(
                service_id,
                organization_id=opts.get("org_id", self.state.selected_org_id),
                role_id=opts.get("role_id"),
            )
            if not resolved:
                return {"kind": "error", "message": f"no model routing for service: {service_id}"}
            return {"kind": "models", "resolved": resolved}
        return {"kind": "error", "message": "Usage: /models [list|providers|bindings|add-provider|add-model|bind|resolve] ..."}

    def _command_bundle(self, args: list[str]) -> dict[str, Any]:
        if not args or args[0] == "help":
            return {
                "kind": "help",
                "message": (
                    "Usage: /bundle apply <spec-file> | /bundle apply-yaml <inline-yaml> | "
                    "/bundle export [domain_pack=<domain>] [output=<file>]"
                ),
            }
        action = args[0]
        if action == "apply":
            if len(args) < 2:
                return {"kind": "error", "message": "Usage: /bundle apply <spec-file>"}
            try:
                spec, base_dir = load_bundle_spec(args[1])
                if "organization" in spec and isinstance(spec["organization"], dict):
                    spec["organization"].setdefault("org_id", self.state.selected_org_id)
                summary = apply_bundle_spec(self.container, spec, base_dir=base_dir)
            except ValueError as exc:
                return {"kind": "error", "message": str(exc)}
            summary["spec_file"] = str(Path(args[1]))
            return {"kind": "bundle", "summary": summary}
        if action == "apply-yaml":
            if len(args) < 2:
                return {"kind": "error", "message": "Usage: /bundle apply-yaml <inline-yaml>"}
            raw = " ".join(args[1:])
            try:
                spec = yaml.safe_load(raw) or {}
                if not isinstance(spec, dict):
                    return {"kind": "error", "message": "inline YAML must parse to an object"}
                if "organization" in spec and isinstance(spec["organization"], dict):
                    spec["organization"].setdefault("org_id", self.state.selected_org_id)
                summary = apply_bundle_spec(self.container, spec, base_dir=None)
            except ValueError as exc:
                return {"kind": "error", "message": str(exc)}
            return {"kind": "bundle", "summary": summary}
        if action == "export":
            opts = _parse_kv_options(args[1:])
            spec = export_bundle_spec(
                self.container,
                organization_id=self.state.selected_org_id,
                domain_pack=opts.get("domain_pack"),
            )
            output_file = opts.get("output")
            payload = yaml.safe_dump(spec, sort_keys=False)
            if output_file:
                Path(output_file).write_text(payload, encoding="utf-8")
                return {"kind": "bundle", "summary": {"exported": True, "output_file": str(Path(output_file))}}
            return {"kind": "bundle_export", "yaml": payload}
        return {"kind": "error", "message": "Usage: /bundle apply|apply-yaml|export ..."}

    def _command_integrations(self, args: list[str]) -> dict[str, Any]:
        action = args[0] if args else "status"
        if action == "status":
            opts = _parse_kv_options(args[1:] if args else [])
            org = self.container.repositories.organization.get_or_create(opts.get("org_id", self.state.selected_org_id))
            effective_opencode_cmd = org.opencode_cmd or self.container.settings.opencode_cmd
            commands = {
                "git": shutil.which("git") is not None,
                "gh": shutil.which("gh") is not None,
                "plantuml": shutil.which("plantuml") is not None,
                "node": shutil.which("node") is not None,
                "java": shutil.which("java") is not None,
                effective_opencode_cmd: shutil.which(effective_opencode_cmd) is not None,
            }
            litellm_configured = bool(org.litellm_base_url and org.litellm_api_key)
            openai_configured = bool(org.openai_api_key)
            return {
                "kind": "integrations",
                "status": {
                    "organization": {"org_id": org.org_id, "name": org.name},
                    "openai": {
                        "enabled": openai_configured or self.container.settings.openai_enabled,
                        "configured": openai_configured,
                        "model": org.openai_model or self.container.settings.openai_model,
                    },
                    "litellm": {
                        "enabled": litellm_configured or self.container.settings.litellm_enabled,
                        "configured": litellm_configured,
                        "base_url": org.litellm_base_url or self.container.settings.litellm_base_url,
                        "default_model": org.litellm_default_model or self.container.settings.litellm_default_model,
                    },
                    "opencode": {
                        "enabled": org.opencode_enabled or self.container.settings.opencode_enabled,
                        "cmd": effective_opencode_cmd,
                        "available": commands.get(effective_opencode_cmd, False),
                    },
                    "commands": commands,
                    "connectors": commands,
                    "model_routing": {
                        "step_execution": self.container.model_router.resolve_public(
                            "step_execution",
                            organization_id=org.org_id,
                        )
                    },
                },
            }
        if action == "health":
            return {"kind": "integrations", "health": connector_health(self.container.settings)}
        if action == "bindings":
            return {
                "kind": "integrations",
                "bindings": self.container.repositories.integration_bindings.list(status="active"),
            }
        return {"kind": "error", "message": "Usage: /integrations [status|health|bindings] ..."}

    def _command_tasks(self, args: list[str]) -> dict[str, Any]:
        if not args or args[0] == "list":
            opts = _parse_kv_options(args[1:] if args else [])
            organization_id = opts.get("organization_id", self.state.selected_org_id)
            limit = 20
            if "limit" in opts:
                try:
                    limit = int(opts["limit"])
                except ValueError:
                    return {"kind": "error", "message": "limit must be an integer"}
            rows = [
                task.model_dump(mode="json")
                for task in self.container.repositories.tasks.list(organization_id)[: max(limit, 0)]
            ]
            return {"kind": "tasks", "items": rows}
        action = args[0]
        if action == "intake":
            opts = _parse_kv_options(args[1:])
            request_parts = [part for part in args[1:] if "=" not in part]
            request = opts.get("request") or " ".join(request_parts).strip()
            if not request:
                return {
                    "kind": "error",
                    "message": (
                        "Usage: /tasks intake <request> [domain_pack=<domain>] [organization_id=<org>] "
                        "[workflow_id=<id>] [workflow_version=<n>] [fanout=true|false] [run=true|false] [trace=true|false]"
                    ),
                }
            domain_pack = opts.get("domain_pack", self.state.selected_domain_pack)
            organization_id = opts.get("organization_id", self.state.selected_org_id)
            workflow_id = opts.get("workflow_id", self.state.selected_workflow_id)
            workflow_version: int | None
            if "workflow_version" in opts:
                try:
                    workflow_version = int(opts["workflow_version"])
                except ValueError:
                    return {"kind": "error", "message": "workflow_version must be an integer"}
            else:
                workflow_version = self.state.selected_workflow_version if workflow_id else None
            try:
                fanout = _parse_bool(opts.get("fanout"), default=False)
                run = _parse_bool(opts.get("run"), default=False)
                include_trace = _parse_bool(opts.get("trace"), default=False)
            except ValueError as exc:
                return {"kind": "error", "message": str(exc)}

            tasks = self._intake_tasks(
                request=request,
                domain_pack=domain_pack,
                organization_id=organization_id,
                workflow_id=workflow_id,
                workflow_version=workflow_version,
                fanout=fanout,
            )
            if run:
                tasks = self._run_tasks(tasks)

            payload: dict[str, Any]
            if len(tasks) == 1:
                payload = {"task": tasks[0].model_dump(mode="json")}
            else:
                payload = {"tasks": [task.model_dump(mode="json") for task in tasks]}

            if include_trace and len(tasks) == 1:
                payload["trace"] = self._trace_for_task(tasks[0].task_id)
            return {"kind": "tasks", **payload}
        if action == "run":
            if len(args) < 2:
                return {"kind": "error", "message": "Usage: /tasks run <task_id> [trace=true|false]"}
            task = self.container.repositories.tasks.get(args[1])
            if not task:
                return {"kind": "error", "message": f"task not found: {args[1]}"}
            if not task.workflow_id or task.workflow_version is None:
                return {"kind": "error", "message": f"task has no selected workflow: {args[1]}"}
            task = self._run_tasks([task])[0]
            payload: dict[str, Any] = {"task": task.model_dump(mode="json")}
            opts = _parse_kv_options(args[2:])
            try:
                include_trace = _parse_bool(opts.get("trace"), default=False)
            except ValueError as exc:
                return {"kind": "error", "message": str(exc)}
            if include_trace:
                payload["trace"] = self._trace_for_task(task.task_id)
            return {"kind": "tasks", **payload}
        if action == "trace":
            if len(args) < 2:
                return {"kind": "error", "message": "Usage: /tasks trace <task_id>"}
            return {"kind": "tasks", "trace": self._trace_for_task(args[1])}
        if action == "events":
            if len(args) < 2:
                return {"kind": "error", "message": "Usage: /tasks events <task_id> [limit=<n>]"}
            opts = _parse_kv_options(args[2:])
            limit = 200
            if "limit" in opts:
                try:
                    limit = int(opts["limit"])
                except ValueError:
                    return {"kind": "error", "message": "limit must be an integer"}
            events = AuditLogService(self.container.repositories).list_task_events(args[1])
            if limit >= 0:
                events = events[:limit]
            return {"kind": "tasks", "events": events}
        if action == "fanin":
            if len(args) < 2:
                return {"kind": "error", "message": "Usage: /tasks fanin <fanout_group>"}
            return {"kind": "tasks", "fanin": self.container.intake_service.fanin_summary(args[1])}
        return {"kind": "error", "message": "Usage: /tasks [list|intake|run|trace|events|fanin] ..."}

    def _command_memory(self, args: list[str]) -> dict[str, Any]:
        if not args:
            return {
                "kind": "error",
                "message": (
                    "Usage: /memory [groups|group-create|memberships|member-add|resolve|query|invalidate] ..."
                ),
            }
        action = args[0]
        if action == "groups":
            opts = _parse_kv_options(args[1:])
            organization_id = opts.get("organization_id", self.state.selected_org_id)
            groups = [
                item.model_dump(mode="json")
                for item in self.container.memory_group_registry.list(
                    organization_id=organization_id,
                    status=opts.get("status", "active"),
                )
            ]
            return {"kind": "memory", "groups": groups}
        if action == "group-create":
            if len(args) < 3:
                return {
                    "kind": "error",
                    "message": (
                        "Usage: /memory group-create <group_id> \"Title\" "
                        "[organization_id=<org>] [visibility=shared|private] [owner_role_id=<role>] [description=<text>]"
                    ),
                }
            group_id = args[1]
            title = args[2]
            opts = _parse_kv_options(args[3:])
            group = MemoryGroupDefinition(
                group_id=group_id,
                organization_id=opts.get("organization_id", self.state.selected_org_id),
                title=title,
                description=opts.get("description"),
                visibility=opts.get("visibility", "shared"),
                owner_role_id=opts.get("owner_role_id"),
                status=opts.get("status", "active"),
            )
            self.container.memory_group_registry.upsert(group)
            return {"kind": "memory", "group": group.model_dump(mode="json")}
        if action == "memberships":
            opts = _parse_kv_options(args[1:])
            organization_id = opts.get("organization_id", self.state.selected_org_id)
            memberships = [
                item.model_dump(mode="json")
                for item in self.container.memory_membership_registry.list(
                    organization_id=organization_id,
                    group_id=opts.get("group_id"),
                    role_id=opts.get("role_id"),
                    status=opts.get("status", "active"),
                )
            ]
            return {"kind": "memory", "memberships": memberships}
        if action == "member-add":
            if len(args) < 3:
                return {
                    "kind": "error",
                    "message": (
                        "Usage: /memory member-add <group_id> <role_id> "
                        "[organization_id=<org>] [access=read|write|read_write]"
                    ),
                }
            group_id = args[1]
            role_id = args[2]
            opts = _parse_kv_options(args[3:])
            membership = MemoryGroupMembership(
                organization_id=opts.get("organization_id", self.state.selected_org_id),
                group_id=group_id,
                role_id=role_id,
                access=opts.get("access", "read_write"),
                status=opts.get("status", "active"),
            )
            self.container.memory_membership_registry.upsert(membership)
            return {"kind": "memory", "membership": membership.model_dump(mode="json")}
        if action == "resolve":
            if len(args) < 2:
                return {
                    "kind": "error",
                    "message": (
                        "Usage: /memory resolve <role_id> "
                        "[organization_id=<org>] [domain_pack=<domain>] [workflow_id=<id>] [workflow_version=<n>]"
                    ),
                }
            role_id = args[1]
            opts = _parse_kv_options(args[2:])
            workflow_id = opts.get("workflow_id", self.state.selected_workflow_id)
            if not workflow_id:
                return {"kind": "error", "message": "workflow_id is required (or select a workflow first)"}
            workflow_version_raw = opts.get("workflow_version")
            if workflow_version_raw is None:
                workflow_version = self.state.selected_workflow_version
            else:
                try:
                    workflow_version = int(workflow_version_raw)
                except ValueError:
                    return {"kind": "error", "message": "workflow_version must be an integer"}
            if workflow_version is None:
                return {"kind": "error", "message": "workflow_version is required (or select a workflow version)"}
            scopes = self.container.memory_topology_service.resolve_scopes(
                organization_id=opts.get("organization_id", self.state.selected_org_id),
                role_id=role_id,
                domain_pack=opts.get("domain_pack", self.state.selected_domain_pack),
                workflow_id=workflow_id,
                workflow_version=workflow_version,
            )
            return {"kind": "memory", "scopes": scopes}
        opts = _parse_kv_options(args[1:])
        organization_id = opts.get("organization_id", self.state.selected_org_id)
        domain_pack = opts.get("domain_pack", self.state.selected_domain_pack)
        workflow_id = opts.get("workflow_id", self.state.selected_workflow_id)
        workflow_version_raw = opts.get("workflow_version")
        workflow_version: int | None = self.state.selected_workflow_version if workflow_version_raw is None else None
        if workflow_version_raw is not None:
            try:
                workflow_version = int(workflow_version_raw)
            except ValueError:
                return {"kind": "error", "message": "workflow_version must be an integer"}
        if not workflow_id or workflow_version is None:
            return {
                "kind": "error",
                "message": "memory operations require workflow_id and workflow_version (or selected workflow)",
            }
        scope = {
            "organization_id": organization_id,
            "domain_pack": domain_pack,
            "workflow_id": workflow_id,
            "workflow_version": workflow_version,
            "role": opts.get("role", "any"),
        }

        if action == "query":
            memory_type = opts.get("memory_type", "episodic")
            try:
                active_only = _parse_bool(opts.get("active_only"), default=True)
            except ValueError as exc:
                return {"kind": "error", "message": str(exc)}
            return {
                "kind": "memory",
                "scope": scope,
                "memory_type": memory_type,
                "items": self.container.memory_service.retrieve(
                    scope,
                    memory_type=memory_type,
                    active_only=active_only,
                ),
            }
        if action == "invalidate":
            try:
                hard = _parse_bool(opts.get("hard"), default=False)
            except ValueError as exc:
                return {"kind": "error", "message": str(exc)}
            changed = self.container.memory_service.invalidate(scope, hard=hard)
            return {"kind": "memory", "ok": True, "changed": changed, "scope": scope, "hard": hard}
        return {
            "kind": "error",
            "message": "Usage: /memory [groups|group-create|memberships|member-add|resolve|query|invalidate] ...",
        }

    def _command_artifacts(self, args: list[str]) -> dict[str, Any]:
        if not args:
            return {"kind": "error", "message": "Usage: /artifacts [list|upsert-file|upsert-yaml] ..."}
        action = args[0]
        if action == "list":
            if len(args) < 2:
                return {
                    "kind": "error",
                    "message": (
                        "Usage: /artifacts list <artifact_type> [organization_id=<org>] [status=<status>] [limit=<n>]"
                    ),
                }
            artifact_type = args[1]
            opts = _parse_kv_options(args[2:])
            organization_id = opts.get("organization_id", self.state.selected_org_id)
            limit = 50
            if "limit" in opts:
                try:
                    limit = int(opts["limit"])
                except ValueError:
                    return {"kind": "error", "message": "limit must be an integer"}
            try:
                items = self.container.artifact_service.list(
                    artifact_type,
                    status=opts.get("status"),
                    organization_id=organization_id,
                )
            except ValueError as exc:
                return {"kind": "error", "message": str(exc)}
            if limit >= 0:
                items = items[:limit]
            return {"kind": "artifacts", "artifact_type": artifact_type, "items": items}
        if action == "upsert-file":
            if len(args) < 3:
                return {"kind": "error", "message": "Usage: /artifacts upsert-file <artifact_type> <payload_file>"}
            artifact_type = args[1]
            source = Path(args[2])
            if not source.exists():
                return {"kind": "error", "message": f"payload file not found: {source}"}
            raw = source.read_text(encoding="utf-8")
            try:
                if source.suffix.lower() == ".json":
                    payload = json.loads(raw)
                else:
                    payload = yaml.safe_load(raw)
            except Exception as exc:
                return {"kind": "error", "message": f"failed to parse payload file: {exc}"}
            if not isinstance(payload, dict):
                return {"kind": "error", "message": "artifact payload must be an object"}
            payload.setdefault("organization_id", self.state.selected_org_id)
            try:
                item = self.container.artifact_service.upsert(artifact_type, payload)
            except ValueError as exc:
                return {"kind": "error", "message": str(exc)}
            return {"kind": "artifacts", "artifact_type": artifact_type, "artifact": item}
        if action == "upsert-yaml":
            if len(args) < 3:
                return {"kind": "error", "message": "Usage: /artifacts upsert-yaml <artifact_type> <inline-yaml>"}
            artifact_type = args[1]
            raw = " ".join(args[2:])
            try:
                payload = yaml.safe_load(raw)
            except Exception as exc:
                return {"kind": "error", "message": f"invalid inline yaml: {exc}"}
            if not isinstance(payload, dict):
                return {"kind": "error", "message": "artifact payload must be an object"}
            payload.setdefault("organization_id", self.state.selected_org_id)
            try:
                item = self.container.artifact_service.upsert(artifact_type, payload)
            except ValueError as exc:
                return {"kind": "error", "message": str(exc)}
            return {"kind": "artifacts", "artifact_type": artifact_type, "artifact": item}
        return {"kind": "error", "message": "Usage: /artifacts [list|upsert-file|upsert-yaml] ..."}

    def _command_state(self, args: list[str]) -> dict[str, Any]:
        if not args or args[0] == "list":
            partition_id = args[1] if len(args) > 1 else None
            items = self.container.state_partition_service.list(partition_id=partition_id, limit=100)
            return {"kind": "state", "items": items}
        action = args[0]
        if action == "get":
            if len(args) < 3:
                return {"kind": "error", "message": "Usage: /state get <partition_id> <key>"}
            data = self.container.state_partition_service.get(args[1], args[2])
            if data is None:
                return {"kind": "error", "message": "state entry not found"}
            return {"kind": "state", "item": data}
        return {"kind": "error", "message": "Usage: /state [list|get] ..."}

    def _handle_chat_message(self, text: str) -> dict[str, Any]:
        lower = text.lower().strip()
        greetings = {"hi", "hello", "hey", "yo", "good morning", "good evening"}
        if lower in greetings or lower.startswith("how does this work"):
            return {"kind": "chat", "message": self._greeting_text()}

        tasks = self._intake_tasks(
            request=text,
            domain_pack=self.state.selected_domain_pack,
            organization_id=self.state.selected_org_id,
            workflow_id=self.state.selected_workflow_id,
            workflow_version=self.state.selected_workflow_version,
            fanout=True,
        )
        tasks = self._run_tasks(tasks)

        if len(tasks) > 1:
            return {
                "kind": "task_batch_result",
                "fanout_count": len(tasks),
                "tasks": [
                    {
                        "task_id": task.task_id,
                        "status": task.current_status.value,
                        "workflow_id": task.workflow_id,
                        "workflow_version": task.workflow_version,
                        "task_object_ref": task.linked_entities.get("task_object_ref"),
                    }
                    for task in tasks
                ],
            }

        task = tasks[0]
        payload = task.model_dump(mode="json")
        return {
            "kind": "task_result",
            "task_id": task.task_id,
            "status": task.current_status.value,
            "workflow_id": task.workflow_id,
            "workflow_version": task.workflow_version,
            "result_summary": task.result_summary,
            "task": payload,
        }

    def _help_text(self) -> str:
        return (
            "Slash commands:\n"
            "  /help\n"
            "  /status\n"
            "  /domain [docs|custom|...]\n"
            "  /organization [list|view|select|create|update|run|runtime|status|stop]\n"
            "    example: /organization create docs \"Docs Org\" litellm_base_url=http://localhost:4000 "
            "litellm_start_cmd=\"docker compose up -d litellm\"\n"
            "  /agents [list|select|create]\n"
            "    example: /agents create docs_maintainer \"Docs Maintainer\" domain_pack=docs "
            "capabilities=docs_context,docs_edit connector=opencode model_id=docs_fast\n"
            "  /workflows [list|select|create|versions|diff|validate-file|publish-file]\n"
            "    example: /workflows create docs_maintenance \"Docs Maintenance\" owned_by=docs_maintainer "
            "domain_pack=docs intent_group=task_authoring required_capabilities=docs_context,docs_edit\n"
            "  /models [list|providers|bindings|add-provider|add-model|bind|resolve]\n"
            "  /bundle apply <spec-file>\n"
            "  /bundle export [domain_pack=<domain>] [output=<file>]\n"
            "  /integrations [status|health|bindings]\n"
            "  /tasks [list|intake|run|trace|events|fanin]\n"
            "  /memory [groups|group-create|memberships|member-add|resolve|query|invalidate]\n"
            "  /artifacts [list|upsert-file|upsert-yaml]\n"
            "  /state [list|get]\n"
            "  /exit\n"
            "Any non-slash message is treated as a task request and executed through Loom."
        )

    def _greeting_text(self) -> str:
        return (
            "Loom chat is workflow-bound orchestration.\n"
            "Use /organization, /agents, and /workflows to configure.\n"
            "Then send a normal message to run a task through the selected workflow.\n"
            "Use /help for examples."
        )


def _render_response(response: dict[str, Any]) -> str:
    kind = response.get("kind")
    if kind == "noop":
        return ""
    if kind in {"error", "help", "chat"}:
        return str(response.get("message", ""))
    if kind == "exit":
        return str(response.get("message", "Bye."))
    if kind == "status":
        return _json(response["state"])
    if kind == "organization":
        if "organization" in response:
            return _json(response["organization"])
        return str(response.get("message", "ok"))
    if kind == "bundle_export":
        return str(response.get("yaml", ""))
    if kind in {
        "organization_list",
        "agents",
        "workflows",
        "domain",
        "models",
        "bundle",
        "integrations",
        "tasks",
        "memory",
        "artifacts",
        "state",
    }:
        return _json({k: v for k, v in response.items() if k != "kind"})
    if kind == "task_batch_result":
        return _json(
            {
                "fanout_count": response.get("fanout_count"),
                "tasks": response.get("tasks", []),
            }
        )
    if kind == "task_result":
        summary = {
            "task_id": response.get("task_id"),
            "status": response.get("status"),
            "workflow_id": response.get("workflow_id"),
            "workflow_version": response.get("workflow_version"),
            "result_summary": response.get("result_summary"),
        }
        return _json(summary)
    return _json(response)


def run_chat_loop(container) -> None:
    session = LoomChatSession(container)
    print("Loom Chat CLI. Type /help for commands.")
    while True:
        try:
            line = input("loom> ")
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            return
        response = session.handle_line(line)
        text = _render_response(response)
        if text:
            print(text)
        if response.get("kind") == "exit":
            return
