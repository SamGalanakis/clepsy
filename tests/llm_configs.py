import os

from clepsy.entities import GoogleAIConfig, OpenAIGenericConfig


google_api_key = os.getenv("GOOGLE_API_KEY")

openrouter_api_key = os.getenv("OPENROUTER_API_KEY")


llm_as_judge_config = (
    GoogleAIConfig(
        model="gemini-2.5-pro",
        api_key=google_api_key,
    )
    if google_api_key
    else None
)


gemini_2_5 = (
    GoogleAIConfig(
        model="gemini-2.5-flash",
        api_key=google_api_key,
    )
    if google_api_key
    else None
)


openrouter_model_names = [
    "openai/gpt-4.1-nano",
    "moonshotai/kimi-vl-a3b-thinking",
    "google/gemma-3-4b-it",
]


def build_openrouter_config(model_name: str) -> OpenAIGenericConfig | None:
    if not openrouter_api_key:
        return None

    return OpenAIGenericConfig(
        model=model_name,
        api_key=openrouter_api_key,
        model_base_url="https://openrouter.ai/api/v1",
    )
