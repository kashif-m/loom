from __future__ import annotations

from typing import Any


class OpenAIAgentsAdapter:
    def __init__(self, *, enabled: bool = False, api_key: str = "", model: str = "gpt-4.1-mini"):
        self.enabled = enabled
        self.api_key = api_key
        self.model = model
        self._client = None
        self._openai_cls = None
        try:
            from openai import OpenAI

            self._openai_cls = OpenAI
        except Exception:
            self._openai_cls = None
            self.enabled = False

        if enabled and self._openai_cls is not None and api_key:
            self._client = self._openai_cls(api_key=api_key)

    def run(
        self,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict[str, Any]] | None = None,
        *,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> dict[str, Any]:
        del tools  # Reserved for future tool use.
        selected_model = model or self.model
        selected_api_key = api_key or self.api_key

        if self._openai_cls is None or not selected_api_key:
            return {
                "ok": True,
                "output": f"mocked-model-output: {user_prompt[:120]}",
                "model": "mock",
                "usage": {"input_tokens": 0, "output_tokens": 0},
            }

        try:
            if self._client is not None and model is None and base_url is None and api_key is None:
                client = self._client
            else:
                kwargs: dict[str, Any] = {"api_key": selected_api_key}
                if base_url:
                    kwargs["base_url"] = base_url
                client = self._openai_cls(**kwargs)

            response = client.chat.completions.create(
                model=selected_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
            )
            output_text = ""
            if response.choices and response.choices[0].message:
                output_text = response.choices[0].message.content or ""
            usage = getattr(response, "usage", None)
            usage_payload = {
                "input_tokens": getattr(usage, "prompt_tokens", 0) if usage else 0,
                "output_tokens": getattr(usage, "completion_tokens", 0) if usage else 0,
            }
            return {
                "ok": True,
                "output": output_text,
                "model": selected_model,
                "usage": usage_payload,
            }
        except Exception as exc:
            return {
                "ok": False,
                "error": str(exc),
                "output": f"model-error-fallback: {user_prompt[:120]}",
                "model": selected_model,
                "usage": {"input_tokens": 0, "output_tokens": 0},
            }
