from clepsy.entities import ImageProcessingApproach, ModelProvider
from clepsy.modules.user_settings.llm_models.router import validate_llm_models_form


def test_validate_requires_image_model_when_vlm_selected() -> None:
    (
        image_provider_error,
        image_base_url_error,
        image_model_error,
        image_api_key_error,
        text_provider_error,
        text_base_url_error,
        text_model_error,
        text_api_key_error,
    ) = validate_llm_models_form(
        image_model_provider=ModelProvider.GOOGLE_AI,
        image_model_base_url=None,
        image_model="",
        text_model_provider=ModelProvider.GOOGLE_AI,
        text_model_base_url=None,
        text_model="gemini-2.0",
        image_processing_approach=ImageProcessingApproach.VLM,
    )

    assert image_provider_error is None
    assert image_base_url_error is None
    assert image_model_error == "Image model name is required"
    assert image_api_key_error is None
    assert text_provider_error is None
    assert text_base_url_error is None
    assert text_model_error is None
    assert text_api_key_error is None


def test_validate_allows_missing_image_model_for_ocr() -> None:
    (
        image_provider_error,
        image_base_url_error,
        image_model_error,
        image_api_key_error,
        text_provider_error,
        text_base_url_error,
        text_model_error,
        text_api_key_error,
    ) = validate_llm_models_form(
        image_model_provider=None,
        image_model_base_url=None,
        image_model="",
        text_model_provider=ModelProvider.GOOGLE_AI,
        text_model_base_url=None,
        text_model="gemini-2.0",
        image_processing_approach=ImageProcessingApproach.OCR,
    )

    assert image_provider_error is None
    assert image_base_url_error is None
    assert image_model_error is None
    assert image_api_key_error is None
    assert text_provider_error is None
    assert text_base_url_error is None
    assert text_model_error is None
    assert text_api_key_error is None


def test_validate_requires_image_provider_when_vlm_selected() -> None:
    (
        image_provider_error,
        _,
        image_model_error,
        _,
        text_provider_error,
        text_base_url_error,
        text_model_error,
        text_api_key_error,
    ) = validate_llm_models_form(
        image_model_provider=None,
        image_model_base_url=None,
        image_model="vision",
        text_model_provider=ModelProvider.GOOGLE_AI,
        text_model_base_url=None,
        text_model="gemini-2.0",
        image_processing_approach=ImageProcessingApproach.VLM,
    )

    assert image_provider_error == "Select an image model provider"
    assert image_model_error is None
    assert text_provider_error is None
    assert text_base_url_error is None
    assert text_model_error is None
    assert text_api_key_error is None
