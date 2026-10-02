import pytest
from backend.normalization.models import NormalizedMessage
from backend.security.pii import (
    PIIBlockedException,
    PIISanitizer,
    PII_STRICTNESS_ORDER,
    resolve_pii_mode,
)
from backend.security.models import PIIEntity, PIISanitizationResult


def test_credit_card_luhn_check():
    # Valid Visa card candidate
    assert PIISanitizer.luhn_checksum_valid("4532015112830366") is True
    # Invalid card number
    assert PIISanitizer.luhn_checksum_valid("4532015112830367") is False
    # Short number
    assert PIISanitizer.luhn_checksum_valid("12345") is False


def test_mask_email():
    text = "Please reach out to support.alice@company-corp.com or bob@gmail.com for help."
    result = PIISanitizer.sanitize(text, mode="mask")
    assert result.has_pii is True
    assert "[REDACTED_EMAIL]" in result.sanitized_text
    assert "support.alice@company-corp.com" not in result.sanitized_text
    assert "bob@gmail.com" not in result.sanitized_text
    assert len(result.detected_entities) == 2


def test_mask_ssn():
    text = "User SSN is 012-34-5678 and another one is 123-45-6789."
    result = PIISanitizer.sanitize(text, mode="mask")
    assert result.has_pii is True
    assert "[REDACTED_SSN]" in result.sanitized_text
    assert "012-34-5678" not in result.sanitized_text
    assert "123-45-6789" not in result.sanitized_text


def test_mask_api_keys_and_secrets():
    text = "Found secret sk-abcdef1234567890abcdef123456 and ghp_1234567890abcdefghijklmnopqrstuvwxyz and cm_live_1234567890abcdef1234567890"
    result = PIISanitizer.sanitize(text, mode="mask")
    assert result.has_pii is True
    assert "[REDACTED_SECRET]" in result.sanitized_text
    assert "sk-abcdef1234567890abcdef123456" not in result.sanitized_text
    assert "ghp_1234567890abcdefghijklmnopqrstuvwxyz" not in result.sanitized_text


def test_mask_phone_and_ip():
    text = "Call me at +1 555-234-5678 or connect to server at 192.168.1.100."
    result = PIISanitizer.sanitize(text, mode="mask")
    assert result.has_pii is True
    assert "[REDACTED_PHONE]" in result.sanitized_text
    assert "[REDACTED_IP]" in result.sanitized_text


def test_block_mode_raises():
    text = "My secret token is sk-1234567890abcdef1234567890."
    with pytest.raises(PIIBlockedException) as exc_info:
        PIISanitizer.sanitize(text, mode="block")
    assert len(exc_info.value.entities) > 0


def test_passthrough_mode():
    text = "Email alice@test.com with key sk-1234567890abcdef1234567890"
    result = PIISanitizer.sanitize(text, mode="passthrough")
    assert result.sanitized_text == text
    assert result.has_pii is False


def test_clean_text_no_pii():
    text = "Explain the difference between QuickSort and MergeSort algorithms in Python."
    result = PIISanitizer.sanitize(text, mode="mask")
    assert result.has_pii is False
    assert result.sanitized_text == text
    assert len(result.detected_entities) == 0


@pytest.mark.parametrize(
    "server,client,expected",
    [
        # Server passthrough: client can escalate to mask or block
        ("passthrough", "passthrough", "passthrough"),
        ("passthrough", "mask", "mask"),
        ("passthrough", "block", "block"),
        ("passthrough", None, "passthrough"),
        ("passthrough", "", "passthrough"),
        ("passthrough", "   ", "passthrough"),
        # Server mask: client cannot downgrade to passthrough, but can escalate to block
        ("mask", "passthrough", "mask"),
        ("mask", "mask", "mask"),
        ("mask", "block", "block"),
        ("mask", None, "mask"),
        ("mask", "", "mask"),
        # Server block: client cannot downgrade to passthrough or mask
        ("block", "passthrough", "block"),
        ("block", "mask", "block"),
        ("block", "block", "block"),
        ("block", None, "block"),
        # Case normalization and whitespace trimming
        ("MASK", "BLOCK", "block"),
        ("mask", "  Passthrough  ", "mask"),
        ("passthrough", " MASK ", "mask"),
    ],
)
def test_resolve_pii_mode_matrix(server, client, expected):
    assert resolve_pii_mode(server, client) == expected


@pytest.mark.parametrize("invalid_mode", ["disable", "off", "0", "none", "invalid", "ALLOW", "bypass"])
def test_resolve_pii_mode_invalid_client_raises(invalid_mode):
    with pytest.raises(ValueError) as exc_info:
        resolve_pii_mode("mask", invalid_mode)
    assert f"Invalid PII mode '{invalid_mode}'" in str(exc_info.value)
    assert "Supported modes" in str(exc_info.value)


@pytest.mark.parametrize("invalid_server_mode", ["", "   ", "invalid", "none", "off", "unknown"])
def test_resolve_pii_mode_invalid_server_raises(invalid_server_mode):
    with pytest.raises(ValueError) as exc_info:
        resolve_pii_mode(invalid_server_mode, "mask")
    assert "Invalid server PII mode" in str(exc_info.value)
    assert "Supported modes" in str(exc_info.value)


@pytest.mark.parametrize("invalid_mode", ["disable", "off", "0", "none", "invalid", "ALLOW", "bypass"])
def test_sanitizer_invalid_mode_raises(invalid_mode):
    with pytest.raises(ValueError) as exc_info:
        PIISanitizer.sanitize("Hello world", mode=invalid_mode)
    assert f"Invalid PII mode '{invalid_mode}'" in str(exc_info.value)
    assert "Supported modes" in str(exc_info.value)


def test_structured_content_array_sanitization():
    content = [
        {"type": "text", "text": "Contact me at alice@company.com or phone +1 555-019-2834"},
        {"type": "image_url", "image_url": {"url": "https://example.com/chart.png"}},
    ]
    sanitized_content, entities = PIISanitizer.sanitize_content(content, mode="mask")
    assert isinstance(sanitized_content, list)
    assert len(entities) == 2
    assert "[REDACTED_EMAIL]" in sanitized_content[0]["text"]
    assert "[REDACTED_PHONE]" in sanitized_content[0]["text"]
    assert "alice@company.com" not in sanitized_content[0]["text"]
    # Image part is preserved untouched
    assert sanitized_content[1] == {"type": "image_url", "image_url": {"url": "https://example.com/chart.png"}}


def test_sanitize_messages_in_place():
    messages = [
        NormalizedMessage(role="system", content="You are a helpful assistant."),
        NormalizedMessage(role="user", content="My SSN is 123-45-6789 and email is bob@test.com"),
        NormalizedMessage(role="assistant", content=None),
        NormalizedMessage(
            role="user",
            content=[{"type": "text", "text": "My server IP is 10.0.0.1"}],
        ),
    ]

    entities = PIISanitizer.sanitize_messages(messages, mode="mask")
    assert len(entities) == 3
    assert messages[0].content == "You are a helpful assistant."
    assert "[REDACTED_SSN]" in messages[1].content
    assert "[REDACTED_EMAIL]" in messages[1].content
    assert "123-45-6789" not in messages[1].content
    assert messages[2].content is None
    assert "[REDACTED_IP]" in messages[3].content[0]["text"]

