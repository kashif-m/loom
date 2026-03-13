from __future__ import annotations

from loom.models import ClassificationResult


class RuleBasedClassifier:
    def __init__(self, workflow_registry):
        self.workflow_registry = workflow_registry

    def classify(self, request: str) -> ClassificationResult:
        text = request.lower()
        if "address" in text and "pr" in text:
            return ClassificationResult(intent_group="pr_review_addressal", confidence=0.9, outcome="supported")
        if "promote" in text and "pr" in text:
            return ClassificationResult(intent_group="pr_promotion", confidence=0.9, outcome="supported")
        if "develop" in text or "implement" in text:
            return ClassificationResult(intent_group="development", confidence=0.75, outcome="supported")
        if "docs" in text or "documentation" in text or "enhance" in text:
            return ClassificationResult(intent_group="task_authoring", confidence=0.8, outcome="supported")
        return ClassificationResult(intent_group="unknown", confidence=0.2, outcome="unsupported")
