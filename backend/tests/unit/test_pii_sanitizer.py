import pytest
from backend.security.pii import PIISanitizer, PIIBlockedException
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
