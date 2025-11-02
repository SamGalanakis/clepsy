from functools import lru_cache
from typing import TypeVar

from baml_py import ClientRegistry
from pydantic import BaseModel

from clepsy.entities import (
    LLMConfig,
    ModelProvider,
)


T = TypeVar("T", bound=BaseModel)
OT = TypeVar("OT", bound=BaseModel)


@lru_cache(maxsize=5)
def create_client_registry(
    llm_config: LLMConfig,
    name: str,
    set_primary: bool = False,
    temperature: float = 0.0,
) -> ClientRegistry:
    cr = ClientRegistry()
    match llm_config.model_provider:
        case ModelProvider.GOOGLE_AI:
            generation_config = {
                "temperature": temperature,
            }

            options = {
                "model": llm_config.model,
                "api_key": llm_config.api_key,
                "generationConfig": generation_config,
            }

            if llm_config.model_base_url:
                options["base_url"] = llm_config.model_base_url

        case ModelProvider.OPENAI:
            options = {
                "model": llm_config.model,
                "api_key": llm_config.api_key,
                "temperature": temperature,
            }
            if llm_config.model_base_url:
                options["base_url"] = llm_config.model_base_url

        case ModelProvider.OPENAI_GENERIC:
            # Generic OpenAI-compatible providers (OpenRouter, Groq, etc.)
            options = {
                "model": llm_config.model,
                "api_key": llm_config.api_key,
                "temperature": temperature,
            }
            if llm_config.model_base_url:
                options["base_url"] = llm_config.model_base_url

        case ModelProvider.ANTHROPIC:
            options = {
                "model": llm_config.model,
                "api_key": llm_config.api_key,
                "temperature": temperature,
            }
            if llm_config.model_base_url:
                options["base_url"] = llm_config.model_base_url

        case _:
            raise ValueError(f"Unsupported model provider: {llm_config.model_provider}")

    cr.add_llm_client(
        name=name,
        provider=llm_config.model_provider,
        options=options,
    )

    if set_primary:
        cr.set_primary(name)

    return cr
