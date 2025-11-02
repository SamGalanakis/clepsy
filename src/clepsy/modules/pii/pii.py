from functools import lru_cache
from pathlib import Path
from typing import Callable

from gliner import GLiNER
from loguru import logger

from clepsy.config import config


@lru_cache
def get_gliner_model(model_name: str, cache_dir: Path) -> GLiNER:
    logger.info(f"Loading GLiNER model '{model_name}'")
    model = GLiNER.from_pretrained(model_name, cache_dir=cache_dir)
    logger.info("GLiNER model loaded")
    return model


def redact_template(entity_type: str) -> str:
    return f"<REDACTED:{entity_type.upper()}>"


def anonymize_text(
    text: str,
    model: GLiNER | None = None,
    entity_types: list[str] | None = None,
    threshold: float = 0.3,
    redact_func: Callable[[str], str] = redact_template,
) -> str:
    if model is None:
        model = get_gliner_model(
            model_name=config.gliner_pii_model,
            cache_dir=config.gliner_cache_dir,
        )
    if entity_types is None:
        entity_types = []

    entities = model.predict_entities(text, labels=entity_types, threshold=threshold)

    # Sort by position to replace from end to start
    entities.sort(key=lambda x: x["start"], reverse=True)

    anonymized = text
    for entity in entities:
        placeholder = redact_func(entity["label"])
        anonymized = (
            anonymized[: entity["start"]] + placeholder + anonymized[entity["end"] :]
        )

    return anonymized


DEFAULT_PII_ENTITY_TYPES = [
    # Personal
    "username",
    "dob",
    "email address",
    "phone number",
    # Location
    "location address",
    "location street",
    "location zip",
    "ip address",
    "mac address",
    # Financial
    "account number",
    "credit card",
    "cvv",
    "iban",
    "tax id",
    "account balance",
    # IDs
    "ssn",
    "passport number",
    "driver license number",
    "identification number",
    # Authentication
    "password",
    "token",
    "api key",
]
