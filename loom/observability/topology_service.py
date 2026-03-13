from __future__ import annotations


class TopologyService:
    def __init__(self, repositories):
        self.repositories = repositories

    def generate_mermaid(self) -> str:
        roles = [row["data"]["role_id"] for row in self.repositories.roles.list(status="active")]
        participants = self.repositories.participants.list(status="active")

        lines = ["flowchart LR"]
        for role in roles:
            lines.append(f"  role_{role}[Role: {role}]")
        for p in participants:
            pid = p["data"]["participant_id"]
            role = p["data"]["role_id"]
            lines.append(f"  participant_{pid}[Participant: {pid}]")
            lines.append(f"  role_{role} --> participant_{pid}")
        return "\n".join(lines)
