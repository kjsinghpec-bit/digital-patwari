from __future__ import annotations

import base64
import os
import time

from google import genai
from google.genai import types
from pydantic import BaseModel

# Transient failure classes worth a bounded retry. Permanent 4xx errors
# (bad request, auth, not found) are never retried.
_TRANSIENT_STATUS_CODES = {408, 429, 500, 502, 503, 504}


class MyLLMAdapter:
    def __init__(
        self,
        client=None,
        model_name: str = "gemini-3.5-flash",
        api_key: str | None = None,
        timeout_seconds: float = 120.0,
        max_retries: int = 2,
    ) -> None:
        key = api_key or os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Export it in your environment before running."
            )
        self.client = client or genai.Client(api_key=key)
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    def _is_transient(self, exc: Exception) -> bool:
        status_code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
        if isinstance(status_code, int):
            return status_code in _TRANSIENT_STATUS_CODES
        return isinstance(exc, (TimeoutError, ConnectionError))

    def extract_structured(self, *, system_prompt: str, user_prompt: str, document_parts: list[dict], json_schema: type[BaseModel]) -> str:
        contents = [user_prompt]
        for part in document_parts:
            contents.append(
                types.Part.from_bytes(
                    data=base64.b64decode(part["base64_data"]),
                    mime_type=part["mime_type"],
                )
            )

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=json_schema,
            temperature=0.0,
            http_options=types.HttpOptions(timeout=int(self.timeout_seconds * 1000)),
        )

        attempt = 0
        while True:
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=contents,
                    config=config,
                )
                return response.text
            except Exception as exc:
                if attempt >= self.max_retries or not self._is_transient(exc):
                    raise
                attempt += 1
                time.sleep(2 ** attempt)
