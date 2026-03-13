from __future__ import annotations


class TaskService:
    def __init__(self, repositories):
        self.repositories = repositories

    def get(self, task_id: str):
        return self.repositories.tasks.get(task_id)

    def save(self, task):
        return self.repositories.tasks.update(task)
