"""Extra throttle scopes.

AI-backed endpoints get their own (much lower) scope: they cost money and hit
an external model provider, so they must not share the generic API budget.
The FastAPI service enforces a second, independent limit keyed on the internal
API key — defence in depth if Django is ever bypassed.
"""
from rest_framework.throttling import UserRateThrottle


class AIRateThrottle(UserRateThrottle):
    scope = "ai"
