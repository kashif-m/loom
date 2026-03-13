from __future__ import annotations

import hashlib
import hmac


class OpenClawRuntimeAdapter:
    def __init__(self, shared_secret: str):
        self.shared_secret = shared_secret.encode("utf-8")

    def sign(self, text: str, session_id: str) -> str:
        payload = f"{session_id}:{text}".encode()
        return hmac.new(self.shared_secret, payload, hashlib.sha256).hexdigest()

    def verify(self, text: str, session_id: str, signature: str) -> bool:
        expected = self.sign(text, session_id)
        return hmac.compare_digest(expected, signature)
