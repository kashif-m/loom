from __future__ import annotations

from loom.models import RuntimeParticipant


class ParticipantResolver:
    def __init__(self, role_registry, capability_registry):
        self.role_registry = role_registry
        self.capability_registry = capability_registry

    def resolve(self, task_id: str, step) -> list[RuntimeParticipant]:
        primary_role = self.role_registry.get(step.owned_by)
        if not primary_role:
            raise ValueError(f"unknown owner role: {step.owned_by}")

        required = set(step.required_capabilities)
        if not required.issubset(set(primary_role.capability_ids)):
            missing = required - set(primary_role.capability_ids)
            raise ValueError(f"owner role missing capabilities: {sorted(missing)}")

        participants = [
            RuntimeParticipant(role_id=primary_role.role_id, capability_ids=primary_role.capability_ids, task_id=task_id)
        ]
        for collaborator in step.participants:
            role = self.role_registry.get(collaborator)
            if not role:
                raise ValueError(f"unknown participant role: {collaborator}")
            participants.append(RuntimeParticipant(role_id=role.role_id, capability_ids=role.capability_ids, task_id=task_id))

        if step.spawn_strategy == "single_owner":
            return participants[:1]
        return participants
