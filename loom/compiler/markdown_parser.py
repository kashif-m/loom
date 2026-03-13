from __future__ import annotations

import re
from collections import defaultdict

from loom.models import ParsedWorkflowDocument


class WorkflowMarkdownParser:
    REQUIRED = [
        "Title",
        "Purpose",
        "Trigger",
        "Required Inputs",
        "Steps",
        "Completion Criteria",
        "Blocked Conditions",
        "Failure Conditions",
        "Rules",
    ]

    def parse(self, markdown: str) -> ParsedWorkflowDocument:
        sections: dict[str, list[str]] = defaultdict(list)
        source_locations: dict[str, int] = {}
        current = None

        for i, line in enumerate(markdown.splitlines(), start=1):
            m = re.match(r"^##\s+(.+)\s*$", line)
            if m:
                current = m.group(1).strip()
                source_locations[current] = i
                continue
            if current:
                sections[current].append(line)

        missing = [k for k in self.REQUIRED if k not in sections]
        if missing:
            raise ValueError(f"missing required sections: {', '.join(missing)}")

        steps = self._parse_steps(sections["Steps"])
        return ParsedWorkflowDocument(
            title=self._compact(sections["Title"]),
            purpose=self._compact(sections["Purpose"]),
            trigger=self._compact(sections["Trigger"]),
            required_inputs=self._listify(sections["Required Inputs"]),
            steps=steps,
            completion_criteria=self._compact(sections["Completion Criteria"]),
            blocked_conditions=self._compact(sections["Blocked Conditions"]),
            failure_conditions=self._compact(sections["Failure Conditions"]),
            rules=self._listify(sections["Rules"]),
            source_locations=source_locations,
        )

    def _compact(self, lines: list[str]) -> str:
        return " ".join(l.strip() for l in lines if l.strip())

    def _listify(self, lines: list[str]) -> list[str]:
        out: list[str] = []
        for line in lines:
            line = line.strip()
            if line.startswith("-"):
                out.append(line.lstrip("- ").strip())
            elif line:
                out.append(line)
        return out

    def _parse_steps(self, lines: list[str]) -> list[dict]:
        steps: list[dict] = []
        current: dict | None = None
        for line in lines:
            text = line.strip()
            if re.match(r"^\d+\.\s+", text):
                if current:
                    steps.append(current)
                current = {"text": re.sub(r"^\d+\.\s+", "", text), "attributes": {}}
            elif current and text.startswith("-") and ":" in text:
                k, v = text.lstrip("- ").split(":", 1)
                current["attributes"][k.strip().lower().replace(" ", "_")] = v.strip()
        if current:
            steps.append(current)
        if not steps:
            raise ValueError("no steps found")
        return steps
