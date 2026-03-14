from __future__ import annotations

from uuid import uuid4

from loom.models import Task, TaskStatus


class IntakeService:
    def __init__(self, repositories, classifier, entity_extractor, selector):
        self.repositories = repositories
        self.classifier = classifier
        self.entity_extractor = entity_extractor
        self.selector = selector

    def intake(
        self,
        request_text: str,
        domain_pack: str = "docs",
        *,
        organization_id: str = "default",
    ) -> Task:
        task = Task(
            raw_request=request_text,
            normalized_request=request_text.strip(),
            domain_pack=domain_pack,
            organization_id=organization_id,
        )
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

    def intake_many(
        self,
        request_text: str,
        *,
        domain_pack: str = "docs",
        workflow_id: str | None = None,
        workflow_version: int | None = None,
        organization_id: str = "default",
    ) -> list[Task]:
        task_objects = self._task_objects(request_text)
        if len(task_objects) <= 1:
            if workflow_id:
                return [
                    self.intake_with_workflow(
                        request_text,
                        workflow_id=workflow_id,
                        workflow_version=workflow_version,
                        domain_pack=domain_pack,
                        organization_id=organization_id,
                    )
                ]
            return [self.intake(request_text, domain_pack=domain_pack, organization_id=organization_id)]

        fanout_group = str(uuid4())
        tasks: list[Task] = []
        for idx, obj in enumerate(task_objects, start=1):
            scoped_request = (
                f"{request_text}\n\n"
                f"[task_object_type={obj['task_object_type']} task_object_ref={obj['task_object_ref']}]"
            )
            if workflow_id:
                task = self.intake_with_workflow(
                    scoped_request,
                    workflow_id=workflow_id,
                    workflow_version=workflow_version,
                    domain_pack=domain_pack,
                    organization_id=organization_id,
                )
            else:
                task = self.intake(scoped_request, domain_pack=domain_pack, organization_id=organization_id)

            task.linked_entities["task_object_type"] = obj["task_object_type"]
            task.linked_entities["task_object_ref"] = obj["task_object_ref"]
            # Keep canonical per-object entity fields aligned with the split task object.
            if obj["task_object_type"] == "document_url":
                task.linked_entities["document_url"] = obj["task_object_ref"]
            if obj["task_object_type"] == "pr_number":
                task.linked_entities["pr_number"] = obj["task_object_ref"]
            task.linked_entities["fanout_group"] = fanout_group
            task.linked_entities["fanout_index"] = str(idx)
            task.linked_entities["fanout_size"] = str(len(task_objects))
            self.repositories.tasks.update(task)
            tasks.append(task)
        return tasks

    def intake_with_workflow(
        self,
        request_text: str,
        *,
        workflow_id: str,
        workflow_version: int | None = None,
        domain_pack: str = "docs",
        organization_id: str = "default",
    ) -> Task:
        task = Task(
            raw_request=request_text,
            normalized_request=request_text.strip(),
            domain_pack=domain_pack,
            organization_id=organization_id,
        )
        task.current_status = TaskStatus.created
        self.repositories.tasks.create(task)
        task.current_status = TaskStatus.triaging
        task.linked_entities = self.entity_extractor.extract(request_text)

        workflow = (
            self.repositories.workflows.get_version(workflow_id, workflow_version)
            if workflow_version is not None
            else self.repositories.workflows.get_active_version(workflow_id)
        )
        if workflow is None:
            requested_version = workflow_version if workflow_version is not None else "active"
            task.current_status = TaskStatus.blocked
            task.result_summary = f"Requested workflow not found: {workflow_id}:{requested_version}"
            self.repositories.tasks.update(task)
            return task

        metadata = workflow.get("metadata") or {}
        workflow_domain = metadata.get("domain_pack")
        if domain_pack and workflow_domain and workflow_domain != domain_pack:
            task.current_status = TaskStatus.blocked
            task.result_summary = (
                f"Workflow/domain mismatch: workflow {workflow_id}:{workflow['version']} "
                f"is in domain '{workflow_domain}', not '{domain_pack}'"
            )
            self.repositories.tasks.update(task)
            return task

        task.workflow_id = workflow_id
        task.workflow_version = workflow["version"]
        task.current_status = TaskStatus.workflow_selected
        self.repositories.tasks.update(task)
        return task

    def _task_objects(self, request_text: str) -> list[dict[str, str]]:
        entities = self.entity_extractor.extract_all(request_text)
        objects: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()

        for url in entities.get("document_urls", []):
            key = ("document_url", url)
            if key not in seen:
                objects.append({"task_object_type": "document_url", "task_object_ref": url})
                seen.add(key)

        for pr in entities.get("pr_numbers", []):
            key = ("pr_number", pr)
            if key not in seen:
                objects.append({"task_object_type": "pr_number", "task_object_ref": pr})
                seen.add(key)

        return objects

    def fanin_summary(self, fanout_group: str) -> dict:
        tasks = [
            t
            for t in self.repositories.tasks.list()
            if t.linked_entities.get("fanout_group") == fanout_group
        ]
        by_status: dict[str, int] = {}
        task_items: list[dict[str, str | None]] = []
        for task in tasks:
            status = task.current_status.value
            by_status[status] = by_status.get(status, 0) + 1
            task_items.append(
                {
                    "task_id": task.task_id,
                    "status": status,
                    "workflow_id": task.workflow_id,
                    "workflow_version": str(task.workflow_version) if task.workflow_version is not None else None,
                    "task_object_type": task.linked_entities.get("task_object_type"),
                    "task_object_ref": task.linked_entities.get("task_object_ref"),
                }
            )

        return {
            "fanout_group": fanout_group,
            "count": len(tasks),
            "by_status": by_status,
            "tasks": task_items,
        }
