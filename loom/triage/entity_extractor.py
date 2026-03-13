from __future__ import annotations

import re


class EntityExtractor:
    def extract(self, request: str) -> dict[str, str]:
        entities: dict[str, str] = {}

        pr_match = re.search(r"\bpr\s*#?(\d+)\b", request, flags=re.IGNORECASE)
        if pr_match:
            entities["pr_number"] = pr_match.group(1)

        url_match = re.search(r"https?://\S+", request)
        if url_match:
            entities["document_url"] = url_match.group(0)

        repo_match = re.search(r"repo(?:sitory)?\s*[:=]\s*([\w./-]+)", request, flags=re.IGNORECASE)
        if repo_match:
            entities["repository"] = repo_match.group(1)

        branch_match = re.search(r"branch\s*[:=]\s*([\w./-]+)", request, flags=re.IGNORECASE)
        if branch_match:
            entities["branch"] = branch_match.group(1)

        return entities
