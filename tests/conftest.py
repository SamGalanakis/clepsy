import pytest

from clepsy.entities import (
    ImageProcessingApproach,
    UserSettings,
)

from .llm_configs import gemini_2_5


@pytest.fixture
def mock_llm_config():
    """Mock LLM configuration for testing - uses real API key from environment"""
    if not gemini_2_5:
        pytest.skip("GOOGLE_API_KEY environment variable not set")
    return gemini_2_5


@pytest.fixture
def mock_user_settings(mock_llm_config):
    """Mock user settings for testing"""
    return UserSettings(
        timezone="UTC",
        image_model_config=mock_llm_config,
        text_model_config=mock_llm_config,
        username="test_user",
        productivity_prompt="Focus on deep work and minimize distractions",
        image_processing_approach=ImageProcessingApproach.VLM,
    )
