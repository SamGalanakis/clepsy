import pytest

from clepsy.modules.pii.pii import anonymize_text


@pytest.mark.pii
def test_anonymize_text_returns_original_when_no_match():
    text = "No sensitive data here."

    redacted = anonymize_text(
        text=text,
        entity_types=["email address"],
        threshold=0.99,
    )

    assert redacted == text


@pytest.mark.pii
def test_anonymize_text_redacts_email_with_default_template():
    text = "Email me at john.doe@example.com"

    redacted = anonymize_text(
        text=text,
        entity_types=["email address"],
        threshold=0.3,
    )

    assert "john.doe@example.com" not in redacted
    assert "<REDACTED:EMAIL ADDRESS>" in redacted


@pytest.mark.pii
def test_anonymize_text_redacts_phone_number():
    text = "Call me at +1-202-555-0131 tomorrow"

    redacted = anonymize_text(
        text=text,
        entity_types=["phone number"],
    )

    assert "202-555-0131" not in redacted
    assert "<REDACTED:PHONE NUMBER>" in redacted


@pytest.mark.pii
def test_anonymize_text_can_use_custom_placeholder():
    text = "SSN: 123-45-6789"

    def blank_placeholder(_: str) -> str:
        return ""

    redacted = anonymize_text(
        text=text,
        entity_types=["ssn"],
        redact_func=blank_placeholder,
    )

    assert "123-45-6789" not in redacted
    assert redacted == "SSN: "


@pytest.mark.pii
def test_anonymize_text_redacts_ip_address():
    text = "Server at 192.168.10.12 is down"

    redacted = anonymize_text(
        text=text,
        entity_types=["ip address"],
    )

    assert "192.168.10.12" not in redacted
    assert "<REDACTED:IP ADDRESS>" in redacted


@pytest.mark.pii
def test_anonymize_text_redacts_credit_card_number():
    text = "Card number 4242 4242 4242 4242 expires 12/29"

    redacted = anonymize_text(
        text=text,
        entity_types=["credit card"],
    )

    assert "4242" not in redacted
    assert "<REDACTED:CREDIT CARD>" in redacted


@pytest.mark.pii
def test_anonymize_text_redacts_api_key():
    text = "API key: sk-test-abc123XYZ"

    redacted = anonymize_text(
        text=text,
        entity_types=["api key"],
    )

    assert "sk-test-abc123XYZ" not in redacted
    assert "<REDACTED:API KEY>" in redacted
