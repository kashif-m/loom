from __future__ import annotations

from loom.models import Task, TaskStatus


class IntakeService:
    def __init__(self, repositories, classifier, entity_extractor, selector):
        self.repositories = repositories
        self.classifier = classifier
        self.entity_extractor = entity_extractor
        self.selector = selector

    def intake(self, request_text: str, domain_pack: str = "docs") -> Task:
        task = Task(raw_request=request_text, normalized_request=request_text.strip(), domain_pack=domain_pack)
        task.current_status = TaskStatus.created
        self.repositories.tasks.create(task)

        task.current_status = TaskStatus.triaging
        classification = self.classifier.classify(request_text)
        entities = self.entity_extractor.extract(request_text)
        task.linked_entities = entities

        selected = self.selector.select(
            classification.intent_group if classification.outcome == "supported" else None,
            domain_pack=domain_pack,
        )
        if not selected:
            if classification.outcome != "supported":
                task.current_status = TaskStatus.blocked
                task.result_summary = (
                    "Unsupported request. Try docs task phrasing such as "
                    "'enhance docs <url>', 'address comments on PR <n>', or 'promote PR <n>'."
                )
            else:
                task.current_status = TaskStatus.awaiting_input
                task.result_summary = (
                    "Workflow not available for detected intent. "
                    "Ensure the relevant workflow is published and active, or provide missing PR/repository details."
                )
            self.repositories.tasks.update(task)
            return task

        workflow_id, version = selected
        task.workflow_id = workflow_id
        task.workflow_version = version
        task.current_status = TaskStatus.workflow_selected
        self.repositories.tasks.update(task)
        return task
