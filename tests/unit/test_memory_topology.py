from pathlib import Path

import pytest

from loom.app.config import Settings
from loom.app.dependency_injection import Container
from loom.models import MemoryGroupDefinition, MemoryGroupMembership, RoleDefinition


def test_memory_topology_resolves_private_and_shared_scopes(tmp_path: Path):
    container = Container(Settings(database_url=f"sqlite:///{tmp_path}/memory-topology.db", disable_scheduler=True))

    container.role_registry.upsert(
        RoleDefinition(
            role_id="parent",
            title="Parent",
            domain_pack="custom",
            capability_ids=[],
            policy_ids=[],
            memory_visibility=[],
            status="active",
        )
    )
    container.role_registry.upsert(
        RoleDefinition(
            role_id="child",
            title="Child",
            domain_pack="custom",
            capability_ids=[],
            policy_ids=[],
            memory_visibility=[],
            status="active",
        )
    )

    container.memory_group_registry.upsert(
        MemoryGroupDefinition(
            group_id="team_shared",
            organization_id="org_a",
            title="Team Shared",
            visibility="shared",
            owner_role_id="parent",
            status="active",
        )
    )
    container.memory_membership_registry.upsert(
        MemoryGroupMembership(
            organization_id="org_a",
            group_id="team_shared",
            role_id="parent",
            access="read_write",
            status="active",
        )
    )
    container.memory_membership_registry.upsert(
        MemoryGroupMembership(
            organization_id="org_a",
            group_id="team_shared",
            role_id="child",
            access="read",
            status="active",
        )
    )

    scopes = container.memory_topology_service.resolve_scopes(
        organization_id="org_a",
        role_id="child",
        domain_pack="custom",
        workflow_id="wf",
        workflow_version=1,
    )
    readable = {scope["memory_group_id"] for scope in scopes["read"]}
    writable = {scope["memory_group_id"] for scope in scopes["write"]}
    assert "team_shared" in readable
    assert "team_shared" not in writable
    assert "private.child" in readable
    assert "private.child" in writable


def test_memory_membership_blocks_cross_org_group_reference(tmp_path: Path):
    container = Container(Settings(database_url=f"sqlite:///{tmp_path}/memory-topology-isolation.db", disable_scheduler=True))
    container.role_registry.upsert(
        RoleDefinition(
            role_id="writer",
            title="Writer",
            domain_pack="custom",
            capability_ids=[],
            policy_ids=[],
            memory_visibility=[],
            status="active",
        )
    )
    container.memory_group_registry.upsert(
        MemoryGroupDefinition(
            group_id="shared_docs",
            organization_id="org_a",
            title="Shared Docs",
            visibility="shared",
            owner_role_id="writer",
            status="active",
        )
    )
    with pytest.raises(KeyError):
        container.memory_membership_registry.upsert(
            MemoryGroupMembership(
                organization_id="org_b",
                group_id="shared_docs",
                role_id="writer",
                access="read_write",
                status="active",
            )
        )
