"""Tests for the human-readable password generator."""

from clepsy.human_readable_pw import generate_typable_password


AMBIG = set("Il1O0|`'\"/\\,;:()[]{}<>")
ALLOWED_SEPARATORS = set("-_.")


def test_generate_typable_password_default_character_set():
    password = generate_typable_password()

    assert any(ch.isalpha() for ch in password)
    assert any(ch.isdigit() for ch in password)

    for ch in password:
        assert ch.islower() or ch.isdigit() or ch in ALLOWED_SEPARATORS
        assert ch not in AMBIG


def test_generate_typable_password_high_entropy():
    password = generate_typable_password(min_entropy_bits=96.0)

    # Basic sanity: higher entropy target should give us a longer string
    assert len(password) >= 16
    assert sum(ch.isdigit() for ch in password) >= 3


def test_generate_typable_password_multiple_calls_unique():
    passwords = {generate_typable_password() for _ in range(20)}
    assert len(passwords) == 20
