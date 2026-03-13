from __future__ import annotations

from loom.models import RuntimeParticipant


class ParticipantRegistry:
    def __init__(self, repositories):
        self.repositories = repositories

    def upsert(self, participant: RuntimeParticipant) -> None:
        self.repositories.participants.upsert(
            participant.participant_id,
            participant.model_dump(),
            status="active" if participant.active else "retired",
        )

    def list_active_for_role(self, role_id: str) -> list[RuntimeParticipant]:
        rows = self.repositories.participants.list(status="active")
        return [RuntimeParticipant(**row["data"]) for row in rows if row["data"].get("role_id") == role_id]
