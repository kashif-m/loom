from __future__ import annotations

import re


class EntityExtractor:
    def extract_all(self, request: str) -> dict[str, list[str]]:
        pr_numbers = re.findall(r"\bpr\s*#?(\d+)\b", request, flags=re.IGNORECASE)
        urls = re.findall(r"https?://\S+", request)
        repositories = re.findall(
            r"repo(?:sitory)?\s*[:=]\s*([\w./-]+)",
            request,
            flags=re.IGNORECASE,
        )
        branches = re.findall(r"branch\s*[:=]\s*([\w./-]+)", request, flags=re.IGNORECASE)
        return {
            "pr_numbers": pr_numbers,
            "document_urls": urls,
            "repositories": repositories,
            "branches": branches,
        }

    def extract(self, request: str) -> dict[str, str]:
        entities: dict[str, str] = {}
        all_entities = self.extract_all(request)
        if all_entities["pr_numbers"]:
            entities["pr_number"] = all_entities["pr_numbers"][0]
        if all_entities["document_urls"]:
            entities["document_url"] = all_entities["document_urls"][0]
        if all_entities["repositories"]:
            entities["repository"] = all_entities["repositories"][0]
        if all_entities["branches"]:
            entities["branch"] = all_entities["branches"][0]

        return entities
