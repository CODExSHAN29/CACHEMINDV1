import hashlib
import json
from typing import Any

from backend.normalization.models import NormalizedInferenceRequest


def canonicalize_data(val: Any) -> Any:
    """
    Recursively canonicalizes data structures:
    - Dicts: Keys are sorted lexicographically, values canonicalized recursively.
    - Lists/Tuples: Sequence order is STRICTLY preserved, items canonicalized recursively.
    - Primitives: Returned directly.
    """
    if isinstance(val, dict):
        return {k: canonicalize_data(v) for k, v in sorted(val.items(), key=lambda item: str(item[0]))}
    elif isinstance(val, (list, tuple)):
        return [canonicalize_data(item) for item in val]
    return val


def canonical_json(data: Any) -> str:
    """
    Serializes data to a deterministic, canonical JSON string:
    - Recursively sorted keys
    - Compact separators (no trailing or leading whitespace around ':' and ',')
    - Explicit UTF-8 (ensure_ascii=False)
    """
    canonical_obj = canonicalize_data(data)
    return json.dumps(
        canonical_obj,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def sha256_json(data: Any) -> str:
    """Computes a SHA-256 hex digest of canonicalized JSON data."""
    canon_str = canonical_json(data)
    return hashlib.sha256(canon_str.encode("utf-8")).hexdigest()


def canonicalize_request(request: NormalizedInferenceRequest) -> str:
    """
    Extracts inference identity attributes from the request and converts
    them to a deterministic canonical JSON string.
    """
    identity_dict = request.to_inference_identity_dict()
    return canonical_json(identity_dict)
