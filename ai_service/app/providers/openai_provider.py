"""OpenAI-backed provider (Chat Completions, JSON responses)."""
from __future__ import annotations

import json

from app.core.config import get_settings
from app.providers.base import AIProvider, CaptionSuggestions, ModerationVerdict, MoodVerdict, ProviderError
from app.providers.http_base import post_json

_MODERATION_SYSTEM = (
    "You are a content safety classifier for a social network. "
    'Reply ONLY with JSON: {"is_safe": bool, "flags": ["toxicity"|"hate"|"spam"|"violence"|"sexual"|"pii"], '
    '"confidence": float between 0 and 1, "reason": short sentence}. '
    "Be conservative: only flag clear violations. Do not flag disagreement, sarcasm or strong opinion alone."
)

_CAPTION_SYSTEM = (
    "You write short social media captions. "
    'Reply ONLY with JSON: {"captions": ["...", "..."]}. '
    "Each caption is at most 120 characters, no hashtags unless asked, no emoji unless the tone allows."
)

_MOOD_SYSTEM = (
    "You estimate the overall tone of a batch of short posts. You are NOT a clinician and must not diagnose. "
    'Reply ONLY with JSON: {"mood_signal": "positive"|"neutral"|"negative", '
    '"suggestion": one gentle sentence}.'
)


class OpenAIProvider(AIProvider):
    name = "openai"

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.openai_api_key:
            raise ProviderError("OPENAI_API_KEY is not configured")
        self.api_key = settings.openai_api_key
        self.model = settings.openai_model
        self.url = f"{settings.openai_base_url.rstrip('/')}/chat/completions"

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    async def _chat(self, system: str, user: str, *, event: str, json_mode: bool = True) -> dict:
        payload: dict = {
            "model": self.model,
            "temperature": 0.2,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        data = await post_json(self.url, headers=self._headers, payload=payload, event=event)
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("unexpected OpenAI response shape") from exc
        try:
            return json.loads(content)
        except ValueError as exc:
            raise ProviderError("model did not return valid JSON") from exc

    async def moderate(self, text: str) -> ModerationVerdict:
        result = await self._chat(_MODERATION_SYSTEM, text, event="provider.openai.moderate")
        flags = [str(f).lower() for f in result.get("flags", []) if str(f)]
        confidence = float(result.get("confidence", 0.5))
        return ModerationVerdict(
            is_safe=bool(result.get("is_safe", True)),
            flags=sorted(set(flags)),
            scores={flag: confidence for flag in flags},
            confidence=max(0.0, min(1.0, confidence)),
            reason=str(result.get("reason", "")),
        )

    async def captions(self, idea: str, tone: str | None, count: int) -> CaptionSuggestions:
        prompt = f"Idea: {idea}\nTone: {tone or 'casual'}\nReturn {count} captions."
        result = await self._chat(_CAPTION_SYSTEM, prompt, event="provider.openai.caption")
        suggestions = [str(item).strip() for item in result.get("captions", []) if str(item).strip()]
        if not suggestions:
            raise ProviderError("model returned no captions")
        return CaptionSuggestions(suggestions=suggestions[:count])

    async def mood(self, texts: list[str]) -> MoodVerdict:
        joined = "\n".join(f"- {text}" for text in texts)
        result = await self._chat(_MOOD_SYSTEM, f"Recent posts:\n{joined}", event="provider.openai.mood")
        signal = str(result.get("mood_signal", "neutral")).lower()
        if signal not in ("positive", "neutral", "negative"):
            signal = "neutral"
        return MoodVerdict(
            signal=signal,  # type: ignore[arg-type]
            suggestion=str(result.get("suggestion", "")),
            positive_ratio=0.0,
            negative_ratio=0.0,
        )
