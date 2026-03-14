from pathlib import Path

from loom.app.config import Settings
from loom.app.dependency_injection import Container
from loom.models import CapabilityDefinition, RoleDefinition


def _markdown(required_capability: str) -> str:
    return f"""
## Title
Validator Flow
## Purpose
Test validator checks.
## Trigger
custom
## Required Inputs
- topic
## Steps
1. Execute
- id: execute
- owned_by: test_role
- required_capabilities: {required_capability}
- on_success: completed
## Completion Criteria
done
## Blocked Conditions
none
## Failure Conditions
none
## Rules
- none
"""


def test_ir_validator_checks_owner_role_capability_compatibility(tmp_path: Path):
    container = Container(Settings(database_url=f"sqlite:///{tmp_path}/validator.db", disable_scheduler=True))

    container.capability_registry.upsert(
        CapabilityDefinition(
            capability_id="missing_cap",
            description="missing",
            connector_binding="none",
            status="active",
        )
    )
    container.role_registry.upsert(
        RoleDefinition(
            role_id="test_role",
            title="Test Role",
            domain_pack="custom",
            capability_ids=[],
            policy_ids=[],
            memory_visibility=[],
            status="active",
        )
    )

    parsed = container.parser.parse(_markdown("missing_cap"))
    compiled = container.compiler.compile("wf_validator", 1, parsed)
    errors = container.ir_validator.validate(compiled)
    assert any("missing capabilities missing_cap" in err for err in errors)


def test_ir_validator_allows_owner_when_required_capability_present(tmp_path: Path):
    container = Container(Settings(database_url=f"sqlite:///{tmp_path}/validator-ok.db", disable_scheduler=True))

    container.capability_registry.upsert(
        CapabilityDefinition(
            capability_id="present_cap",
            description="present",
            connector_binding="none",
            status="active",
        )
    )
    container.role_registry.upsert(
        RoleDefinition(
            role_id="test_role",
            title="Test Role",
            domain_pack="custom",
            capability_ids=["present_cap"],
            policy_ids=[],
            memory_visibility=[],
            status="active",
        )
    )

    parsed = container.parser.parse(_markdown("present_cap"))
    compiled = container.compiler.compile("wf_validator_ok", 1, parsed)
    errors = container.ir_validator.validate(compiled)
    assert not any("missing capabilities" in err for err in errors)
