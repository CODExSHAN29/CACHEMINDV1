"""
Guardrail Arbiter — Prevents Dangerous False-Positive Semantic Cache Hits.

Semantic caching by cosine similarity alone has a critical failure mode:
Opposite queries can have high similarity (>0.90) because they share context words:

    "Cancel my subscription"  <-- cosine: 0.93 -->  "Renew my subscription"
    "Refund $50 to my account" <-- cosine: 0.94 -->  "Refund $500 to my account"
    "What was the score in 2020?" <-- cosine: 0.92 --> "What was the score in 2024?"

The Guardrail Arbiter enforces deterministic pre-checks before an L2 hit
is returned to the client.

Checks performed:
1. System Prompt Exact Match — System instructions must match character-for-character
2. Negation / Action Polarity — Words indicating opposing actions must match
3. Numbers Match — All numbers in the prompt must match exactly
4. Dates Match — Extracted dates must match exactly
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple


@dataclass(frozen=True)
class GuardrailDecision:
    """
    Result of guardrail arbiter evaluation.

    Attributes:
        passed: True if all checks pass and it's safe to return the L2 hit
        reason: "PASS" or description of the first failing check
        failed_checks: List of check names that failed (e.g., ["negation", "number"])
        checks_passed: List of check names that passed
    """
    passed: bool
    reason: str
    failed_checks: List[str] = field(default_factory=list)
    checks_passed: List[str] = field(default_factory=list)


class GuardrailArbiter:
    """
    Deterministic safety evaluator for semantic cache candidate hits.

    Enforces the four safety pillars from Section 5.5 of the system design spec.
    """

    # --- Negation & Action Word Dictionaries ---
    # Words that invert or significantly change the intent of an action
    NEGATION_WORDS: Set[str] = {
        "not", "no", "never", "none", "neither", "nor", "nowhere",
        "without", "hardly", "scarcely", "barely", "don't", "dont",
        "doesn't", "doesnt", "didn't", "didnt", "won't", "wont",
        "wouldn't", "wouldnt", "shouldn't", "shouldnt", "can't", "cant",
        "cannot", "couldn't", "couldnt", "isn't", "isnt", "aren't", "arent",
        "wasn't", "wasnt", "weren't", "werent", "haven't", "havent",
        "hasn't", "hasnt", "hadn't", "hadnt",
    }

    # Paired opposite action verbs — if one has word A and other has word B, reject!
    OPPOSING_ACTION_PAIRS: List[Tuple[Set[str], Set[str]]] = [
        ({"cancel", "cancellation", "abort", "revoke", "terminate", "stop", "disable", "turn off"},
         {"renew", "renewal", "continue", "resume", "activate", "start", "enable", "turn on"}),
        ({"delete", "remove", "erase", "drop", "purge", "destroy", "clear"},
         {"create", "add", "insert", "new", "build", "make", "generate", "append"}),
        ({"increase", "raise", "boost", "elevate", "grow", "upgrade", "higher"},
         {"decrease", "lower", "reduce", "drop", "cut", "downgrade", "less"}),
        ({"buy", "purchase", "order", "subscribe"},
         {"sell", "refund", "return", "unsubscribe"}),
        ({"approve", "accept", "agree", "confirm", "allow", "permit"},
         {"reject", "decline", "deny", "refuse", "disallow", "forbid"}),
        ({"lock", "block", "restrict", "protect"},
         {"unlock", "unblock", "unrestrict", "expose"}),
        ({"success", "succeed", "pass", "win"},
         {"fail", "failure", "lose", "error"}),
        ({"enable", "enabled", "on"},
         {"disable", "disabled", "off"}),
    ]

    def __init__(
        self,
        strict_numbers: bool = True,
        strict_dates: bool = True,
        strict_negations: bool = True,
        strict_system_prompt: bool = True,
    ) -> None:
        self.strict_numbers = strict_numbers
        self.strict_dates = strict_dates
        self.strict_negations = strict_negations
        self.strict_system_prompt = strict_system_prompt

    async def evaluate(
        self,
        incoming_text: str,
        candidate_text: str,
        incoming_system_prompt: Optional[str] = None,
        candidate_system_prompt: Optional[str] = None,
    ) -> GuardrailDecision:
        """
        Evaluate whether a candidate hit is safe to return for an incoming query.

        All checks must pass for the decision to be PASS.

        Args:
            incoming_text: The user message in the current request
            candidate_text: The user message that produced the cached response
            incoming_system_prompt: System message in current request (if any)
            candidate_system_prompt: System message in cached request (if any)

        Returns:
            GuardrailDecision with passed=True/False and detailed reasons
        """
        failed: List[str] = []
        passed: List[str] = []

        # 1. System Prompt Exact Match
        if self.strict_system_prompt:
            sp_incoming = (incoming_system_prompt or "").strip()
            sp_candidate = (candidate_system_prompt or "").strip()
            if sp_incoming != sp_candidate:
                failed.append("system_prompt")
            else:
                passed.append("system_prompt")

        # 2. Negation & Opposing Action Check
        if self.strict_negations:
            neg_passed, neg_reason = self._check_negations_and_actions(
                incoming_text, candidate_text
            )
            if not neg_passed:
                failed.append(f"negation ({neg_reason})")
            else:
                passed.append("negation")

        # 3. Number Match
        if self.strict_numbers:
            num_passed, num_reason = self._check_numbers(incoming_text, candidate_text)
            if not num_passed:
                failed.append(f"number ({num_reason})")
            else:
                passed.append("number")

        # 4. Date Match
        if self.strict_dates:
            date_passed, date_reason = self._check_dates(incoming_text, candidate_text)
            if not date_passed:
                failed.append(f"date ({date_reason})")
            else:
                passed.append("date")

        # Build final decision
        is_safe = len(failed) == 0
        if is_safe:
            reason = "PASS"
        else:
            reason = f"FAIL: {'; '.join(failed)}"

        return GuardrailDecision(
            passed=is_safe,
            reason=reason,
            failed_checks=failed,
            checks_passed=passed,
        )

    # ---------- Internal Safety Checks ----------

    def _tokenize_lower(self, text: str) -> List[str]:
        """Simple word tokenization for negation and keyword checks."""
        return re.findall(r"\b[a-z']+\b", text.lower())

    def _check_negations_and_actions(
        self, text_a: str, text_b: str
    ) -> Tuple[bool, str]:
        """
        Validates negation parity and checks for opposing action verb pairs.
        """
        tokens_a = set(self._tokenize_lower(text_a))
        tokens_b = set(self._tokenize_lower(text_b))

        # Check 1: Explicit negation words parity
        neg_a = tokens_a & self.NEGATION_WORDS
        neg_b = tokens_b & self.NEGATION_WORDS

        # If one has negation words and the other has none -> MISMATCH!
        if bool(neg_a) != bool(neg_b):
            return False, f"negation mismatch: '{neg_a}' vs '{neg_b}'"

        # Check 2: Opposing action pairs
        # If text_a contains words from set A and text_b contains words from set B (or vice versa) -> REJECT!
        for set_pos, set_neg in self.OPPOSING_ACTION_PAIRS:
            a_has_pos = bool(tokens_a & set_pos)
            a_has_neg = bool(tokens_a & set_neg)
            b_has_pos = bool(tokens_b & set_pos)
            b_has_neg = bool(tokens_b & set_neg)

            # Direct opposition: A has POS, B has NEG (e.g., A='renew', B='cancel')
            if (a_has_pos and b_has_neg) or (a_has_neg and b_has_pos):
                word_a = (tokens_a & set_pos) | (tokens_a & set_neg)
                word_b = (tokens_b & set_pos) | (tokens_b & set_neg)
                return False, f"opposing actions detected: '{word_a}' vs '{word_b}'"

        return True, "ok"

    def _extract_numbers(self, text: str) -> Set[str]:
        """
        Extracts numbers from text (integers, floats, currency amounts, percentages).
        Normalizes: "$50" -> "50", "50.0" -> "50", "1,000" -> "1000"
        """
        # Match currency, percentages, floats, integers
        # Pattern handles: $50, 50%, 50.5, 1,000, etc.
        raw_matches = re.findall(r"[\$€£¥]?\b\d+(?:,\d{3})*(?:\.\d+)?%?\b", text)
        cleaned: Set[str] = set()
        for m in raw_matches:
            # Strip currency symbols, commas, percent
            clean = re.sub(r"[^\d.]", "", m)
            if clean:
                # Normalize float vs int: "50.0" -> "50"
                try:
                    val = float(clean)
                    if val.is_integer():
                        cleaned.add(str(int(val)))
                    else:
                        cleaned.add(str(val))
                except ValueError:
                    cleaned.add(clean)
        return cleaned

    def _check_numbers(self, text_a: str, text_b: str) -> Tuple[bool, str]:
        """
        Ensures all numeric values match exactly between both texts.
        """
        nums_a = self._extract_numbers(text_a)
        nums_b = self._extract_numbers(text_b)

        if nums_a != nums_b:
            diff = nums_a.symmetric_difference(nums_b)
            return False, f"number mismatch: '{nums_a}' vs '{nums_b}' (diff: {diff})"

        return True, "ok"

    def _extract_dates(self, text: str) -> Set[str]:
        """
        Extracts dates, years, and month-year combinations from text.
        """
        dates: Set[str] = set()

        # ISO format: 2024-01-15
        iso_dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", text)
        dates.update(iso_dates)

        # US format: 01/15/2024 or 1/15/24
        us_dates = re.findall(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", text)
        dates.update(us_dates)

        # Standalone years: 1900-2099
        years = re.findall(r"\b(19\d{2}|20\d{2})\b", text)
        dates.update(years)

        # Named month patterns: "January 2024", "Jan 15, 2024"
        months = (
            "january|february|march|april|may|june|july|august|september|"
            "october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec"
        )
        named_dates = re.findall(
            rf"\b(?:{months})\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?\b",
            text,
            re.IGNORECASE,
        )
        dates.update([d.lower() for d in named_dates])

        return dates

    def _check_dates(self, text_a: str, text_b: str) -> Tuple[bool, str]:
        """
        Ensures all date/year references match between both texts.
        """
        dates_a = self._extract_dates(text_a)
        dates_b = self._extract_dates(text_b)

        if dates_a != dates_b:
            diff = dates_a.symmetric_difference(dates_b)
            return False, f"date mismatch: '{dates_a}' vs '{dates_b}' (diff: {diff})"

        return True, "ok"


_guardrail_arbiter_instance: Optional[GuardrailArbiter] = None


def get_guardrail_arbiter() -> GuardrailArbiter:
    """Returns singleton GuardrailArbiter instance."""
    global _guardrail_arbiter_instance
    if _guardrail_arbiter_instance is None:
        _guardrail_arbiter_instance = GuardrailArbiter()
    return _guardrail_arbiter_instance


def set_guardrail_arbiter(arbiter: GuardrailArbiter) -> None:
    """Explicitly sets or overrides guardrail arbiter (for tests)."""
    global _guardrail_arbiter_instance
    _guardrail_arbiter_instance = arbiter
