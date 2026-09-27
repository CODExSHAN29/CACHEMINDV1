from dataclasses import dataclass, field
from typing import List


@dataclass
class PIIEntity:
    entity_type: str  # e.g., "credit_card", "ssn", "email", "phone", "api_key", "ip_address"
    matched_text: str
    start: int
    end: int
    mask: str


@dataclass
class PIISanitizationResult:
    sanitized_text: str
    detected_entities: List[PIIEntity] = field(default_factory=list)
    has_pii: bool = False
