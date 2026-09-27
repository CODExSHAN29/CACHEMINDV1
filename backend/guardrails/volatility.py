"""
Volatility Engine — Dynamic TTL Classification for Semantic Cache Entries.

Classifies incoming user prompts into volatility tiers that determine
how long an L2 semantic cache entry remains valid:

- volatile   : 0–300s TTL  (rapidly changing data: prices, stock quotes, live scores)
- semi-static : 86400s (24h) TTL  (frequently updated: news, weather, reviews)
- evergreen  : 2592000s (30d) TTL  (stable: how-to guides, conceptual answers)

Classification is performed via deterministic keyword/regex heuristics,
ensuring no external API calls are needed.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Pattern


class VolatilityTier(str, Enum):
    """Classification tiers determining TTL duration."""
    VOLATILE = "volatile"
    SEMI_STATIC = "semi-static"
    EVERGREEN = "evergreen"

    @property
    def ttl_seconds(self) -> int:
        """Returns the default TTL for this tier."""
        if self is VolatilityTier.VOLATILE:
            return 300      # 5 minutes
        elif self is VolatilityTier.SEMI_STATIC:
            return 86400    # 24 hours
        else:
            return 2592000  # 30 days


@dataclass(frozen=True)
class VolatilityClassification:
    """
    Result of volatility classification for a given text.

    Attributes:
        tier: The classified volatility tier
        confidence: Confidence score [0.0, 1.0]
        matched_keywords: Keywords that triggered the classification
        ttl_seconds: The TTL derived from the tier
        reason: Human-readable explanation
    """
    tier: VolatilityTier
    confidence: float
    matched_keywords: List[str] = field(default_factory=list)
    ttl_seconds: int = 86400
    reason: str = ""


class VolatilityEngine:
    """
    Deterministic keyword-based volatility classifier.

    Uses regex patterns and keyword lists to classify text into
    volatility tiers without any external dependencies.
    """

    # --- Volatile Keywords: rapidly changing data ---
    VOLATILE_KEYWORDS: List[str] = [
        # Financial data
        "stock price", "share price", "current price", "market cap",
        "bitcoin price", "eth price", "crypto price", "exchange rate",
        "stock market", "nyse", "nasdaq", "sp 500", "s&p 500",
        "bond yield", "interest rate", "fed rate", "federal reserve",
        "inflation rate", "cpi", "gdp growth",
        # Real-time data
        "live score", "live map", "real-time", "current temperature",
        "traffic update", "flight status", "weather forecast",
        "breaking news", "just in", "developing story",
        # Sports
        "game score", "quarter score", "inning score", "match score",
        "player stats", "standings", "playoff bracket",
        # Currency/conversion
        "convert usd", "convert eur", "currency converter",
        "exchange rate today",
        # A/B testing / optimization
        "ab test", "split test", "conversion rate", "click-through rate",
        # User-specific ephemeral
        "last login", "session id", "cart total", "shipping status",
        "order status", "delivery tracking",
    ]

    # --- Semi-Static Keywords: updated regularly but not instantly ---
    SEMI_STATIC_KEYWORDS: List[str] = [
        # News / media
        "news article", "current events", "today's news", "headlines",
        "recent news", "latest news", "media coverage",
        # Reviews / ratings
        "product review", "movie review", "book review",
        "customer reviews", "user reviews", "rating",
        # Weather / environment
        "weather", "temperature", "forecast", "humidity", "wind speed",
        # Sports schedules
        "schedule", "game schedule", "match schedule",
        # Company data
        "company profile", "quarterly earnings", "annual report",
        "market share", "industry report",
        # Health
        "drug information", "side effects", "dosage",
        # Local / regional
        "local news", "city news", "regional",
        # Technology
        "new release", "software version", "latest version",
        "patch notes", "update log",
    ]

    # --- Evergreen Keywords: stable, long-term validity ---
    EVERGREEN_KEYWORDS: List[str] = [
        # Education / how-to
        "how to", "tutorial", "guide", "lesson", "course",
        "explained", "definition", "what is", "meaning of",
        # Concepts / theory
        "theory", "concept", "principle", "fundamental", "basics of",
        "introduction to", "overview of", "explain",
        # History / reference
        "history of", "when was", "who invented", "origin of",
        # Reference / encyclopedia
        "definition", "synonym", "antonym", "grammar rule",
        "spell check", "style guide", "formatting",
        # Science / math
        "formula", "equation", "theorem", "proof",
        "scientific method", "chemical element",
        # Programming reference
        "api documentation", "function reference", "syntax",
        "code example", "best practice", "design pattern",
        # General knowledge
        "fact", "trivia", "general knowledge", "fun fact",
        "did you know", "by the way",
    ]

    # --- Patterns for detecting volatile data indicators ---
    PRICE_PATTERNS: List[Pattern[str]] = [
        re.compile(r"\$\d+(?:\.\d+)?", re.IGNORECASE),  # $50, $19.99
        re.compile(r"\b(?:price|cost|rate|fee|charge)\b", re.IGNORECASE),
        re.compile(r"\b(?:today|current|now|latest)\b.*\b(?:price|rate|value)\b", re.IGNORECASE),
    ]

    # --- Time-sensitivity indicators ---
    TIME_SENSITIVE_PATTERNS: List[Pattern[str]] = [
        re.compile(r"\btoday\b", re.IGNORECASE),
        re.compile(r"\bnow\b", re.IGNORECASE),
        re.compile(r"\bcurrent\b", re.IGNORECASE),
        re.compile(r"\blatest\b", re.IGNORECASE),
        re.compile(r"\bthis (?:week|month|year|quarter)\b", re.IGNORECASE),
        re.compile(r"\b(as of|as-of)\b", re.IGNORECASE),
    ]

    def __init__(
        self,
        volatile_keywords: Optional[List[str]] = None,
        semi_static_keywords: Optional[List[str]] = None,
        evergreen_keywords: Optional[List[str]] = None,
        default_tier: VolatilityTier = VolatilityTier.SEMI_STATIC,
    ) -> None:
        self.volatile_keywords = [k.lower() for k in (volatile_keywords or self.VOLATILE_KEYWORDS)]
        self.semi_static_keywords = [k.lower() for k in (semi_static_keywords or self.SEMI_STATIC_KEYWORDS)]
        self.evergreen_keywords = [k.lower() for k in (evergreen_keywords or self.EVERGREEN_KEYWORDS)]
        self.default_tier = default_tier

    async def classify(self, text: str) -> VolatilityClassification:
        """
        Classify text into a volatility tier.

        Process:
        1. Check for volatile keywords/patterns → if matched, classify as volatile
        2. Check for semi-static keywords → if matched, classify as semi-static
        3. Check for evergreen keywords → if matched, classify as evergreen
        4. Default → semi-static (conservative)

        Args:
            text: User prompt to classify

        Returns:
            VolatilityClassification with tier, confidence, and TTL
        """
        text_lower = text.lower()
        matched: List[str] = []

        # Check volatile first (highest priority)
        volatile_matches = self._match_keywords(text_lower, self.volatile_keywords)
        if volatile_matches:
            matched.extend(volatile_matches)
            # Also check price patterns
            for pattern in self.PRICE_PATTERNS:
                if pattern.search(text):
                    matched.append(f"pattern:{pattern.pattern[:30]}")
                    break
            # Check time-sensitive patterns
            for pattern in self.TIME_SENSITIVE_PATTERNS:
                if pattern.search(text):
                    matched.append(f"pattern:{pattern.pattern[:30]}")
                    break

            return VolatilityClassification(
                tier=VolatilityTier.VOLATILE,
                confidence=self._compute_confidence(matched, len(volatile_matches)),
                matched_keywords=matched,
                ttl_seconds=VolatilityTier.VOLATILE.ttl_seconds,
                reason=f"Classified as volatile due to: {', '.join(matched[:5])}",
            )

        # Check semi-static
        semi_matches = self._match_keywords(text_lower, self.semi_static_keywords)
        if semi_matches:
            matched.extend(semi_matches)
            return VolatilityClassification(
                tier=VolatilityTier.SEMI_STATIC,
                confidence=self._compute_confidence(matched, len(semi_matches)),
                matched_keywords=matched,
                ttl_seconds=VolatilityTier.SEMI_STATIC.ttl_seconds,
                reason=f"Classified as semi-static due to: {', '.join(matched[:5])}",
            )

        # Check evergreen
        evergreen_matches = self._match_keywords(text_lower, self.evergreen_keywords)
        if evergreen_matches:
            matched.extend(evergreen_matches)
            return VolatilityClassification(
                tier=VolatilityTier.EVERGREEN,
                confidence=self._compute_confidence(matched, len(evergreen_matches)),
                matched_keywords=matched,
                ttl_seconds=VolatilityTier.EVERGREEN.ttl_seconds,
                reason=f"Classified as evergreen due to: {', '.join(matched[:5])}",
            )

        # Default tier
        return VolatilityClassification(
            tier=self.default_tier,
            confidence=0.5,
            matched_keywords=[],
            ttl_seconds=self.default_tier.ttl_seconds,
            reason=f"No specific keywords matched; default tier: {self.default_tier.value}",
        )

    async def get_ttl(self, text: str) -> int:
        """
        Quick convenience: classify text and return the TTL in seconds.
        """
        classification = await self.classify(text)
        return classification.ttl_seconds

    # ---------- Internal Helpers ----------

    def _match_keywords(self, text_lower: str, keywords: List[str]) -> List[str]:
        """Returns list of matched keywords (max 10 for reporting)."""
        matched: List[str] = []
        for kw in keywords:
            if kw in text_lower:
                matched.append(kw)
                if len(matched) >= 10:
                    break
        return matched

    def _compute_confidence(self, matched: List[str], keyword_count: int) -> float:
        """
        Computes confidence based on number of keyword matches.
        More matches → higher confidence (capped at 0.95).
        """
        if keyword_count == 0:
            return 0.5
        base = min(0.5 + (keyword_count * 0.1), 0.95)
        return round(base, 2)


# Module-level singleton
_volatility_engine_instance: Optional[VolatilityEngine] = None


def get_volatility_engine() -> VolatilityEngine:
    """Returns singleton VolatilityEngine instance."""
    global _volatility_engine_instance
    if _volatility_engine_instance is None:
        _volatility_engine_instance = VolatilityEngine()
    return _volatility_engine_instance


def set_volatility_engine(engine: VolatilityEngine) -> None:
    """Explicitly sets or overrides volatility engine (for tests)."""
    global _volatility_engine_instance
    _volatility_engine_instance = engine
