"""Gemini client wrapper with timeouts, retries with exponential backoff and model fallback."""
from __future__ import annotations

import logging
import random
import time
from functools import lru_cache
from typing import Iterator

from ..config import get_settings

log = logging.getLogger(__name__)

RETRYABLE_CODES = {408, 429, 500, 502, 503, 504}


class LLMUnavailable(RuntimeError):
    pass


def _code(exc: Exception) -> int | None:
    for attr in ("code", "status_code"):
        v = getattr(exc, attr, None)
        if isinstance(v, int):
            return v
    return None


class GeminiLLM:
    def __init__(self):
        from google import genai
        from google.genai import types

        s = get_settings()
        if not s.gemini_enabled:
            raise LLMUnavailable("GEMINI_API_KEY is not configured")
        self._types = types
        self.settings = s
        self.client = genai.Client(
            api_key=s.gemini_api_key.get_secret_value(),
            http_options=types.HttpOptions(timeout=s.gemini_timeout_s * 1000))
        self.model = s.gemini_model

    def _config(self, system: str, max_tokens: int | None, temperature: float | None,
                model: str | None = None):
        model = model or self.model
        thinking = None
        if model.startswith("gemini-3.8-flash"):
            thinking = self._types.ThinkingConfig(thinking_level="LOW")
        elif model.startswith("gemini-3.1-flash-lite"):
            thinking = self._types.ThinkingConfig(thinking_level="MINIMAL")
        return self._types.GenerateContentConfig(
            system_instruction=system,
            temperature=self.settings.gemini_temperature if temperature is None else temperature,
            max_output_tokens=max_tokens or self.settings.gemini_max_output_tokens,
            thinking_config=thinking,
        )

    def _models(self) -> list[str]:
        models = [self.model]
        if self.settings.gemini_fallback_model and self.settings.gemini_fallback_model != self.model:
            models.append(self.settings.gemini_fallback_model)
        return models

    def stream(self, prompt: str, system: str, max_tokens: int | None = None,
               temperature: float | None = None) -> Iterator[str]:
        """Yields text deltas. Retries only before the first token has been emitted."""
        last_exc: Exception | None = None
        for model in self._models():
            for attempt in range(self.settings.gemini_max_retries):
                emitted = False
                try:
                    finish_reason = None
                    for chunk in self.client.models.generate_content_stream(
                            model=model, contents=prompt,
                            config=self._config(system, max_tokens, temperature, model)):
                        text = getattr(chunk, "text", None)
                        if text:
                            emitted = True
                            yield text
                        for candidate in getattr(chunk, "candidates", None) or []:
                            reason = getattr(candidate, "finish_reason", None)
                            if reason:
                                finish_reason = getattr(reason, "name", str(reason)).split(".")[-1]
                    if finish_reason and finish_reason != "STOP":
                        raise LLMUnavailable(f"Gemini response did not finish normally ({finish_reason})")
                    if not emitted:
                        raise LLMUnavailable("Gemini returned no answer text")
                    return
                except Exception as exc:  # noqa: BLE001 - SDK raises several types
                    last_exc = exc
                    code = _code(exc)
                    log.warning("gemini call failed", extra={"extra_fields": {
                        "model": model, "attempt": attempt + 1, "code": code,
                        "error": str(exc)[:300]}})
                    if emitted:
                        raise LLMUnavailable(f"Gemini stream interrupted: {exc}") from exc
                    if code in (400, 401, 403):
                        raise LLMUnavailable(f"Gemini rejected the request ({code}).") from exc
                    if code == 404:
                        break  # unknown model -> try fallback model
                    if code is not None and code not in RETRYABLE_CODES:
                        break
                    time.sleep(min(8.0, (2 ** attempt) + random.random()))
        raise LLMUnavailable(f"Gemini unavailable after retries: {last_exc}")

    def complete(self, prompt: str, system: str, max_tokens: int | None = 300,
                 temperature: float | None = 0.0) -> str:
        return "".join(self.stream(prompt, system, max_tokens, temperature)).strip()

    def list_models(self) -> list[str]:
        return [m.name for m in self.client.models.list()]


@lru_cache
def get_llm() -> GeminiLLM | None:
    try:
        return GeminiLLM()
    except LLMUnavailable:
        return None
    except Exception as exc:  # pragma: no cover
        log.error("could not initialise Gemini", extra={"extra_fields": {"error": str(exc)}})
        return None
