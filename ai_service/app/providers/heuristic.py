"""Local heuristic provider: a small, deterministic lexicon model.

Why ship this at all?

* **Availability.** Moderation sits in the write path of every post. If the
  hosted model is down or unconfigured, we degrade to this instead of failing.
* **Cost.** It answers the overwhelming majority of obviously-clean posts for
  free; hosted calls can then be reserved for borderline content.
* **Testability.** Deterministic output makes the service testable offline.

It is deliberately conservative: it flags obvious cases and otherwise returns
`is_safe=True` with a mid-range confidence, because a false block is far worse
than a missed edge case that a human can review.
"""
from __future__ import annotations

import re

from app.providers.base import AIProvider, CaptionSuggestions, ModerationVerdict, MoodVerdict

_TOXIC = {
    "idiot", "stupid", "moron", "loser", "shut up", "dumb", "pathetic", "trash",
    "bakwas", "bewakoof", "gadha",
}
_HATE = {
    "hate you", "i hate", "kill you", "die", "everyone hates",
    "nafrat", "marna chahiye",
}
_SPAM_PATTERNS = (
    re.compile(r"(https?://\S+\s*){3,}", re.IGNORECASE),
    re.compile(r"\b(free|win|prize|cash|lottery)\b.{0,40}\b(click|dm|link|now)\b", re.IGNORECASE),
    re.compile(r"(.)\1{7,}"),
)
_NEGATIVE = {
    "tired", "exhausted", "lonely", "alone", "hopeless", "anxious", "stressed",
    "sad", "depressed", "crying", "failed", "failure", "broken", "empty", "numb",
    "udaas", "akela", "thak gaya", "himmat",
}
_POSITIVE = {
    "happy", "grateful", "excited", "proud", "loved", "amazing", "great", "blessed",
    "win", "progress", "thankful", "joy", "khush", "maza",
}

_TONE_TEMPLATES = {
    "casual": ["{idea} — and honestly? worth it.", "just {idea}. that's the post.", "{idea}, no notes."],
    "witty": ["{idea}: 1, my sleep schedule: 0.", "told myself one {idea}. that was a lie.",
              "{idea}. no further questions."],
    "inspirational": ["every {idea} is proof you showed up.", "small {idea}, big momentum.",
                      "the {idea} nobody saw coming."],
    "professional": ["{idea} — lessons learned and what's next.", "shipping {idea}: a short recap.",
                     "three takeaways from {idea}."],
}
_DEFAULT_TEMPLATES = _TONE_TEMPLATES["casual"]

_POSITIVE_SUGGESTION = "Momentum looks good — keep sharing what works."
_NEUTRAL_SUGGESTION = "Nothing stands out either way. Nothing to change."
_NEGATIVE_SUGGESTION = (
    "A lot of heavier posts lately. A short walk, some sleep, or a message to someone you trust "
    "can help. If it keeps up, talking to a professional is a good idea too."
)


class HeuristicProvider(AIProvider):
    name = "heuristic"

    def __init__(self, toxicity_threshold: float = 0.6, spam_threshold: float = 0.7) -> None:
        self.toxicity_threshold = toxicity_threshold
        self.spam_threshold = spam_threshold

    # -- moderation ------------------------------------------------------
    async def moderate(self, text: str) -> ModerationVerdict:
        lowered = text.lower()
        scores: dict[str, float] = {}

        toxic_hits = sum(1 for word in _TOXIC if word in lowered)
        hate_hits = sum(1 for word in _HATE if word in lowered)
        spam_hits = sum(1 for pattern in _SPAM_PATTERNS if pattern.search(text))

        # Weights are tuned so two distinct insults clear the 0.6 toxicity bar
        # while a single mild word does not (false positives are costlier than
        # a miss a human reviewer will still see in the feed).
        scores["toxicity"] = min(1.0, 0.35 * toxic_hits + 0.2 * hate_hits)
        scores["hate"] = min(1.0, 0.55 * hate_hits)
        scores["spam"] = min(1.0, 0.6 * spam_hits)

        flags = [
            category
            for category, score in scores.items()
            if score >= (self.spam_threshold if category == "spam" else self.toxicity_threshold)
        ]
        # Any hate-speech hit is treated seriously even below the numeric bar.
        if hate_hits and "hate" not in flags:
            flags.append("hate")

        confidence = max(scores.values()) if scores else 0.5
        reason = (
            "Flagged for: " + ", ".join(sorted(flags))
            if flags
            else "No known toxicity, hate or spam patterns matched."
        )
        return ModerationVerdict(
            is_safe=not flags,
            flags=sorted(set(flags)),
            scores=scores,
            confidence=round(min(1.0, confidence), 3),
            reason=reason,
        )

    # -- captions --------------------------------------------------------
    async def captions(self, idea: str, tone: str | None, count: int) -> CaptionSuggestions:
        templates = _TONE_TEMPLATES.get(tone or "", _DEFAULT_TEMPLATES)
        return CaptionSuggestions(suggestions=[t.format(idea=idea) for t in templates[:count]])

    # -- mood ------------------------------------------------------------
    async def mood(self, texts: list[str]) -> MoodVerdict:
        positive_hits = sum(1 for text in texts if any(w in text.lower() for w in _POSITIVE))
        negative_hits = sum(1 for text in texts if any(w in text.lower() for w in _NEGATIVE))
        total = max(1, len(texts))
        positive_ratio = round(positive_hits / total, 3)
        negative_ratio = round(negative_hits / total, 3)

        if negative_ratio >= 0.4 and negative_ratio > positive_ratio:
            signal, suggestion = "negative", _NEGATIVE_SUGGESTION
        elif positive_ratio >= 0.4 and positive_ratio > negative_ratio:
            signal, suggestion = "positive", _POSITIVE_SUGGESTION
        else:
            signal, suggestion = "neutral", _NEUTRAL_SUGGESTION

        return MoodVerdict(
            signal=signal,
            suggestion=suggestion,
            positive_ratio=positive_ratio,
            negative_ratio=negative_ratio,
        )
