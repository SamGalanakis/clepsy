from __future__ import annotations

from clepsy.config import config
from clepsy.modules.pii.pii import DEFAULT_PII_ENTITY_TYPES, anonymize_text


def sanitize_text(text: str | None) -> str | None:
    """Sanitize PII from text using the shared PII module (synchronous)."""
    if not text:
        return text
    return anonymize_text(
        text=text,
        entity_types=DEFAULT_PII_ENTITY_TYPES,
        threshold=config.gliner_pii_threshold,
    )
