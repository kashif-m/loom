from __future__ import annotations


class WorkflowSelector:
    def __init__(self, workflow_registry):
        self.workflow_registry = workflow_registry

    def select(self, intent_group: str | None, domain_pack: str | None = None) -> tuple[str, int] | None:
        active = self.workflow_registry.list_active()
        if intent_group:
            for item in active:
                metadata = item.get("metadata", {})
                if metadata.get("intent_group") != intent_group:
                    continue
                if domain_pack and metadata.get("domain_pack") != domain_pack:
                    continue
                return item["workflow_id"], item["version"]

        if domain_pack:
            domain_candidates = [
                item
                for item in active
                if item.get("metadata", {}).get("domain_pack") == domain_pack
            ]
            if len(domain_candidates) == 1:
                candidate = domain_candidates[0]
                return candidate["workflow_id"], candidate["version"]
        return None
