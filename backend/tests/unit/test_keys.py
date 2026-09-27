from backend.auth.keys import generate_api_key, hash_api_key, verify_api_key


def test_generate_api_key():
    raw_key, prefix, key_hash = generate_api_key("cm_live_")
    assert raw_key.startswith("cm_live_")
    # Prefix is at least 16 chars
    assert len(prefix) == 16
    assert prefix == raw_key[:16]
    # Hash is SHA-256 (64 hex characters)
    assert len(key_hash) == 64
    assert hash_api_key(raw_key) == key_hash


def test_verify_api_key():
    raw_key, prefix, key_hash = generate_api_key("cm_live_")
    assert verify_api_key(raw_key, key_hash) is True
    assert verify_api_key(raw_key + "tampered", key_hash) is False
    assert verify_api_key("cm_live_completely_wrong_key", key_hash) is False
