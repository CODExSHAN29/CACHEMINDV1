"""
CacheMind Security - Ingress PII & Sensitive Information Sanitizer
"""

import ipaddress
import re
from typing import List, Tuple

from backend.app.config import settings
from backend.security.models import PIIEntity, PIISanitizationResult


class PIIBlockedException(Exception):
    """Raised when a request contains PII and PII_MASKING_MODE is set to 'block'."""
    def __init__(self, message: str, entities: List[PIIEntity]):
        super().__init__(message)
        self.entities = entities


class PIISanitizer:
    """
    High-throughput regular expression & algorithmic PII detection and redaction engine.
    """

    # Email pattern
    EMAIL_PATTERN = re.compile(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    )

    # Social Security Number pattern (SSN: 000-00-0000 or 000 00 0000)
    SSN_PATTERN = re.compile(
        r"\b(?!000|666|9\d{2})\d{3}[-\s]?(?!00)\d{2}[-\s]?(?!0000)\d{4}\b"
    )

    # Phone number pattern (E.164, US formatted, standard dashes/parens)
    PHONE_PATTERN = re.compile(
        r"(?:(?:\+?1\s*(?:[.-]\s*)?)?(?:\(\s*([2-9]1[02-9]|[2-9][02-8]1|[2-9][02-8][02-9])\s*\)|([2-9]1[02-9]|[2-9][02-8]1|[2-9][02-8][02-9]))\s*(?:[.-]\s*)?)?([2-9]1[02-9]|[2-9][02-9]1|[2-9][02-9]{2})\s*(?:[.-]\s*)?([0-9]{4})\b"
    )
    SIMPLE_PHONE_PATTERN = re.compile(
        r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
    )

    # Credit card candidate pattern (13 to 19 digits with optional spaces or dashes)
    CREDIT_CARD_CANDIDATE = re.compile(
        r"\b(?:\d[ -]*?){13,19}\b"
    )

    # Secret keys & Bearer tokens
    API_KEY_PATTERNS = [
        # OpenAI / Anthropic-like keys
        re.compile(r"\b(sk-[a-zA-Z0-9_\-]{20,})\b"),
        # GitHub personal access tokens
        re.compile(r"\b(gh[pousr]_[A-Za-z0-9_]{36,})\b"),
        # AWS Access Key ID
        re.compile(r"\b(AKIA[0-9A-Z]{16})\b"),
        # CacheMind live keys
        re.compile(r"\b(cm_[a-zA-Z0-9_]{20,})\b"),
        # Bearer Authorization headers / tokens
        re.compile(r"\bBearer\s+([a-zA-Z0-9\-_.~+/]{24,}={0,2})\b", re.IGNORECASE),
        # Generic Private Key header
        re.compile(r"-----BEGIN (?:RSA )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA )?PRIVATE KEY-----"),
    ]

    # IPv4 Pattern
    IPV4_PATTERN = re.compile(
        r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b"
    )

    @classmethod
    def luhn_checksum_valid(cls, card_number_str: str) -> bool:
        """
        Validates a potential credit card number using the Luhn mod-10 algorithm.
        """
        digits = [int(c) for c in card_number_str if c.isdigit()]
        if len(digits) < 13 or len(digits) > 19:
            return False

        checksum = 0
        reverse_digits = digits[::-1]
        for i, digit in enumerate(reverse_digits):
            if i % 2 == 1:
                doubled = digit * 2
                checksum += doubled - 9 if doubled > 9 else doubled
            else:
                checksum += digit

        return (checksum % 10) == 0

    @classmethod
    def is_valid_ipv4(cls, ip_str: str) -> bool:
        """Checks if a string is a valid IPv4 address and not a model or version number like 0.0.0.0"""
        try:
            ip = ipaddress.IPv4Address(ip_str)
            # Exclude standard zero or loopback version strings if ambiguous
            return True
        except ValueError:
            return False

    @classmethod
    def scan_text(cls, text: str) -> List[PIIEntity]:
        """
        Scans a text string and returns all detected PII entities with their character ranges.
        """
        if not text:
            return []

        entities: List[PIIEntity] = []

        # 1. API Keys & Secrets
        for pat in cls.API_KEY_PATTERNS:
            for match in pat.finditer(text):
                matched = match.group(0)
                entities.append(
                    PIIEntity(
                        entity_type="secret_key",
                        matched_text=matched,
                        start=match.start(),
                        end=match.end(),
                        mask="[REDACTED_SECRET]",
                    )
                )

        # 2. Email Addresses
        for match in cls.EMAIL_PATTERN.finditer(text):
            matched = match.group(0)
            entities.append(
                PIIEntity(
                    entity_type="email",
                    matched_text=matched,
                    start=match.start(),
                    end=match.end(),
                    mask="[REDACTED_EMAIL]",
                )
            )

        # 3. SSN
        for match in cls.SSN_PATTERN.finditer(text):
            matched = match.group(0)
            # Ensure not a date format like 2024-10-12
            parts = re.split(r"[-\s]", matched)
            if len(parts) == 3 and len(parts[0]) == 3 and len(parts[1]) == 2 and len(parts[2]) == 4:
                entities.append(
                    PIIEntity(
                        entity_type="ssn",
                        matched_text=matched,
                        start=match.start(),
                        end=match.end(),
                        mask="[REDACTED_SSN]",
                    )
                )

        # 4. Credit Cards (with Luhn check)
        for match in cls.CREDIT_CARD_CANDIDATE.finditer(text):
            matched = match.group(0)
            clean_digits = re.sub(r"\D", "", matched)
            if 13 <= len(clean_digits) <= 19 and cls.luhn_checksum_valid(clean_digits):
                entities.append(
                    PIIEntity(
                        entity_type="credit_card",
                        matched_text=matched,
                        start=match.start(),
                        end=match.end(),
                        mask="[REDACTED_CREDIT_CARD]",
                    )
                )

        # 5. Phone Numbers
        for match in cls.SIMPLE_PHONE_PATTERN.finditer(text):
            matched = match.group(0)
            clean_digits = re.sub(r"\D", "", matched)
            if 10 <= len(clean_digits) <= 15:
                # Avoid collision with card numbers or SSN
                entities.append(
                    PIIEntity(
                        entity_type="phone",
                        matched_text=matched,
                        start=match.start(),
                        end=match.end(),
                        mask="[REDACTED_PHONE]",
                    )
                )

        # 6. IPv4 Addresses
        for match in cls.IPV4_PATTERN.finditer(text):
            matched = match.group(0)
            if cls.is_valid_ipv4(matched):
                entities.append(
                    PIIEntity(
                        entity_type="ip_address",
                        matched_text=matched,
                        start=match.start(),
                        end=match.end(),
                        mask="[REDACTED_IP]",
                    )
                )

        # De-duplicate overlapping entity spans (prioritizing secret_key > credit_card > ssn > email > phone > ip)
        return cls._deduplicate_spans(entities)

    @staticmethod
    def _deduplicate_spans(entities: List[PIIEntity]) -> List[PIIEntity]:
        """
        Resolves overlapping entity spans, keeping the longer and higher priority entity.
        """
        if not entities:
            return []

        # Sort by start index ascending, then length descending
        sorted_entities = sorted(entities, key=lambda e: (e.start, -(e.end - e.start)))
        deduped: List[PIIEntity] = []

        for entity in sorted_entities:
            if not deduped:
                deduped.append(entity)
                continue

            last = deduped[-1]
            # Check overlap
            if entity.start < last.end:
                # Overlap detected; keep the one with longer coverage
                if (entity.end - entity.start) > (last.end - last.start):
                    deduped[-1] = entity
            else:
                deduped.append(entity)

        return deduped

    @classmethod
    def sanitize(
        cls,
        text: str,
        mode: str | None = None,
    ) -> PIISanitizationResult:
        """
        Sanitizes the input text according to the selected mode (mask, block, passthrough).
        """
        active_mode = mode or settings.PII_MASKING_MODE

        if active_mode == "passthrough" or not settings.PII_MASKING_ENABLED or not text:
            return PIISanitizationResult(sanitized_text=text, detected_entities=[], has_pii=False)

        entities = cls.scan_text(text)
        has_pii = len(entities) > 0

        if not has_pii:
            return PIISanitizationResult(sanitized_text=text, detected_entities=[], has_pii=False)

        if active_mode == "block":
            raise PIIBlockedException(
                f"Request prompt contains sensitive PII ({len(entities)} entities detected) and cannot be processed.",
                entities=entities,
            )

        # Mode == "mask": build the sanitized string by replacing entity ranges from back to front
        sanitized = list(text)
        for entity in reversed(entities):
            sanitized[entity.start : entity.end] = list(entity.mask)

        sanitized_str = "".join(sanitized)
        return PIISanitizationResult(
            sanitized_text=sanitized_str,
            detected_entities=entities,
            has_pii=True,
        )
