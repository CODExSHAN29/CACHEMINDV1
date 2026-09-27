import pytest
from backend.normalization.canonicalizer import (
    canonical_json,
    canonicalize_data,
    canonicalize_request,
    sha256_json,
)
from backend.normalization.models import (
    NormalizedFunctionCall,
    NormalizedInferenceRequest,
    NormalizedMessage,
    NormalizedToolCall,
)
from backend.normalization.openai_adapter import OpenAIAdapter


def test_dict_key_sorting_invariance():
    dict1 = {"b": 2, "a": 1, "nested": {"z": 26, "y": 25}}
    dict2 = {"a": 1, "b": 2, "nested": {"y": 25, "z": 26}}
    assert canonical_json(dict1) == canonical_json(dict2)
    assert sha256_json(dict1) == sha256_json(dict2)


def test_list_order_preservation():
    # Array ordering must be strictly preserved (A -> B != B -> A)
    list1 = [{"role": "user", "content": "1"}, {"role": "assistant", "content": "2"}]
    list2 = [{"role": "assistant", "content": "2"}, {"role": "user", "content": "1"}]
    assert canonical_json(list1) != canonical_json(list2)
    assert sha256_json(list1) != sha256_json(list2)


def test_transport_fields_excluded_from_inference_identity():
    # stream=True vs stream=False must produce IDENTICAL canonical representation
    req1 = NormalizedInferenceRequest(
        model="gpt-4o",
        messages=[NormalizedMessage(role="user", content="Explain quantum physics")],
        stream=False,
        timeout=30.0,
        client_request_id="req_12345",
        user="user_alice",
    )
    req2 = NormalizedInferenceRequest(
        model="gpt-4o",
        messages=[NormalizedMessage(role="user", content="Explain quantum physics")],
        stream=True,
        timeout=60.0,
        client_request_id="req_99999",
        user="user_bob",
    )
    assert canonicalize_request(req1) == canonicalize_request(req2)
    assert sha256_json(req1.to_inference_identity_dict()) == sha256_json(
        req2.to_inference_identity_dict()
    )


def test_temperature_and_seed_sensitivity():
    req_base = NormalizedInferenceRequest(
        model="gpt-4o",
        messages=[NormalizedMessage(role="user", content="Hello")],
        temperature=0.0,
    )
    req_diff_temp = NormalizedInferenceRequest(
        model="gpt-4o",
        messages=[NormalizedMessage(role="user", content="Hello")],
        temperature=0.7,
    )
    req_diff_seed = NormalizedInferenceRequest(
        model="gpt-4o",
        messages=[NormalizedMessage(role="user", content="Hello")],
        temperature=0.0,
        seed=42,
    )

    canon_base = canonicalize_request(req_base)
    canon_diff_temp = canonicalize_request(req_diff_temp)
    canon_diff_seed = canonicalize_request(req_diff_seed)

    assert canon_base != canon_diff_temp
    assert canon_base != canon_diff_seed


def test_tool_call_canonicalization():
    tool_call1 = NormalizedToolCall(
        id="call_1",
        function=NormalizedFunctionCall(name="get_weather", arguments='{"city":"Tokyo"}'),
    )
    msg1 = NormalizedMessage(role="assistant", tool_calls=[tool_call1])

    req1 = NormalizedInferenceRequest(model="gpt-4o", messages=[msg1])
    canon1 = canonicalize_request(req1)
    assert "get_weather" in canon1
    assert "Tokyo" in canon1


def test_unicode_preservation():
    payload = {"greeting": "こんにちは世界", "emoji": "🚀 CacheMind"}
    canon = canonical_json(payload)
    assert "こんにちは世界" in canon
    assert "🚀 CacheMind" in canon
