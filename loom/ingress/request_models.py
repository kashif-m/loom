from __future__ import annotations

from pydantic import BaseModel


class FFRequest(BaseModel):
    request: str
    domain_pack: str = "docs"
    async_run: bool = False


class AdminWorkflowPublishRequest(BaseModel):
    workflow_id: str
    version: int
    title: str
    domain_pack: str
    intent_group: str
    markdown: str
    activate: bool = True


class AdminInvalidateMemoryRequest(BaseModel):
    organization_id: str = "default"
    domain_pack: str
    workflow_id: str
    workflow_version: int
    role: str = "any"
    hard: bool = False
