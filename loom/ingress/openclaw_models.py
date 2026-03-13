from __future__ import annotations

from pydantic import BaseModel


class OpenClawFFRequest(BaseModel):
    text: str
    session_id: str
    user_id: str | None = None
    stream: bool = True
    signature: str


class OpenClawEvent(BaseModel):
    event: str
    payload: dict
