"""Hugging Face Inference API provider.

Moderation uses a multi-label toxicity classifier (e.g. `unitary/toxic-bert`);
captions and mood use a text-generation model. Labels returned by the model are
normalised onto our own flag vocabulary so downstream code stays stable even if
the model is swapped.
"""
from __future__ import annotations

import json

from app.core.config import get_settings
from app.providers.base import AIProvider, CaptionSuggestions, ModerationVerdict, MoodVerdict, ProviderError
from app.providers.http_base import post_json

_LABEL_MAP = {
    "toxic": "toxicity",
    "toxicity": "toxicity",
    "severe_toxic": "toxicity",
    "hate_speech": "hate",
    "hate": "hate",
    "identity_hate": "hate",
    "abuse": "toxicity",
    "insult": "toxicity",
    "obscene": "toxicity",
    "spam": "spam",
    "threat": "violence",
    "violent": "violence",
    "sexual": "sexual",
    "pii": "pii",
}


class HuggingFaceProvider(AIProvider):
    name = "huggingface"

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.hf_api_token:
            raise ProviderError("HF_API_TOKEN is not configured")
        self.token = settings.hf_api_token
        self.base_url = settings.hf_base_url.rstrip("/")
        self.moderation_model = settings.hf_moderation_model
        self.generation_model = settings.hf_generation_model

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    async def moderate(self, text: str) -> ModerationVerdict:
        settings = get_settings()
        data = await post_json(
            f"{self.base_url}/{self.moderation_model}",
            headers=self._headers,
            payload={"inputs": text, "options": {"wait_for_model": True}},
            event="provider.hf.moderate",
        )
        rows = data[0] if isinstance(data, list) and data and isinstance(data[0], list) else data
        if not isinstance(rows, list):
            raise ProviderError("unexpected HF moderation payload")

        scores: dict[str, float] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            category = _LABEL_MAP.get(str(row.get("label", "")).lower())
            if category:
                scores[category] = max(scores.get(category, 0.0), float(row.get("score", 0.0)))

        flags = sorted(
            category
            for category, score in scores.items()
            if score >= settings.toxicity_threshold
        )
        confidence = max(scores.values()) if scores else 0.5
        return ModerationVerdict(
            is_safe=not flags,
            flags=flags,
            scores=scores,
            confidence=round(min(1.0, confidence), 3),
            reason=(
                "Flagged for: " + ", ".join(flags) if flags else "Below all safety thresholds."
            ),
        )

    async def _generate(self, prompt: str, *, event: str, max_new_tokens: int = 90) -> str:
        data = await post_json(
            f"{self.base_url}/{self.generation_model}",
            headers=self._headers,
            payload={
                "inputs": prompt,
                "parameters": {
                    "max_new_tokens": max_new_tokens,
                    "temperature": 0.7,
                    "return_full_text": False,
                },
                "options": {"wait_for_model": True},
            },
            event=event,
        )
        if isinstance(data, list) and data and isinstance(data[0], dict):
            return str(data[0].get("generated_text", ""))
        raise ProviderError("unexpected HF generation payload")

    async def captions(self, idea: str, tone: str | None, count: int) -> CaptionSuggestions:
        prompt = (
            f"Write {count} distinct short social media captions about: {idea}. "
            f"Tone: {tone or 'casual'}. Return a JSON array of strings."
        )
        raw = await self._generate(prompt, event="provider.hf.caption")
        suggestions = _extract_json_list(raw)
        if not suggestions:
            suggestions = [line.strip("-• ").strip() for line in raw.splitlines() if line.strip()]
        suggestions = [s for s in suggestions if s][:count]
        if not suggestions:
            raise ProviderError("model returned no captions")
        return CaptionSuggestions(suggestions=suggestions)

    async def mood(self, texts: list[str]) -> MoodVerdict:
        joined = "\n".join(f"- {text}" for text in texts[:30])
        prompt = (
            "Estimate the overall tone (positive, neutral or negative) of these posts. "
            "Do not diagnose anything. Reply with JSON: "
            '{"mood_signal": "...", "suggestion": "one gentle sentence"}\n\n' + joined
        )
        raw = await self._generate(prompt, event="provider.hf.mood", max_new_tokens=120)
        payload = _extract_json_object(raw)
        signal = str(payload.get("mood_signal", "neutral")).lower()
        if signal not in ("positive", "neutral", "negative"):
            signal = "neutral"
        return MoodVerdict(
            signal=signal,  # type: ignore[arg-type]
            suggestion=str(payload.get("suggestion", "")),
            positive_ratio=0.0,
            negative_ratio=0.0,
        )


def _extract_json_list(raw: str) -> list[str]:
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return []
    try:
        parsed = json.loads(raw[start : end + 1])
    except ValueError:
        return []
    return [str(item).strip() for item in parsed if str(item).strip()] if isinstance(parsed, list) else []


def _extract_json_object(raw: str) -> dict:
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        parsed = json.loads(raw[start : end + 1])
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
