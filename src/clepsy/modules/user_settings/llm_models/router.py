import json

from fastapi import APIRouter, Depends, Form, status
from fastapi.responses import HTMLResponse
from loguru import logger

from baml_client import b
import baml_client.types as baml_types
from clepsy.auth.auth import encrypt_secret
from clepsy.central_cache import central_cache, user_settings_ttl
from clepsy.config import config
from clepsy.db.db import get_db_connection
from clepsy.db.deps import get_user_settings_optional
from clepsy.db.queries import update_user_settings as update_user_settings_query
from clepsy.entities import (
    AADS,
    AnthropicConfig,
    GoogleAIConfig,
    ImageProcessingApproach,
    ModelProvider,
    OpenAIConfig,
    OpenAIGenericConfig,
    UserSettings,
)
from clepsy.llm import create_client_registry
from clepsy.modules.user_settings.llm_models.page import (
    build_llm_test_modal,
    create_llm_models_page,
)


router = APIRouter()


def non_empty(s: str | None) -> bool:
    return bool(s and s.strip())


def validate_llm_models_form(
    *,
    image_model_provider: ModelProvider | None,
    image_model_base_url: str | None,
    image_model: str | None,
    text_model_provider: ModelProvider,
    text_model_base_url: str | None,
    text_model: str,
    image_processing_approach: ImageProcessingApproach,
) -> tuple[
    str | None,
    str | None,
    str | None,
    str | None,
    str | None,
    str | None,
    str | None,
    str | None,
]:
    image_provider_error = image_base_url_error = image_model_error = (
        image_api_key_error
    ) = None
    text_provider_error = text_base_url_error = text_model_error = (
        text_api_key_error
    ) = None

    require_image_model = image_processing_approach == ImageProcessingApproach.VLM

    if require_image_model:
        if not image_model_provider:
            image_provider_error = "Select an image model provider"
        if not non_empty(image_model):
            image_model_error = "Image model name is required"

    if image_model_base_url not in (None, "") and not (
        image_model_base_url.startswith("http://")
        or image_model_base_url.startswith("https://")
    ):
        image_base_url_error = "Base URL must start with http:// or https://"

    if not text_model_provider:
        text_provider_error = "Select a text model provider"
    if not non_empty(text_model):
        text_model_error = "Text model name is required"
    if text_model_base_url not in (None, "") and not (
        text_model_base_url.startswith("http://")
        or text_model_base_url.startswith("https://")
    ):
        text_base_url_error = "Base URL must start with http:// or https://"

    return (
        image_provider_error,
        image_base_url_error,
        image_model_error,
        image_api_key_error,
        text_provider_error,
        text_base_url_error,
        text_model_error,
        text_api_key_error,
    )


@router.post("/user-settings/llm_models")
async def update_llm_models_settings(
    image_model_provider: ModelProvider = Form(...),
    image_model_base_url: str | None = Form(None),
    image_model: str = Form(...),
    image_model_api_key: str | None = Form(None),
    text_model_provider: ModelProvider = Form(...),
    text_model_base_url: str | None = Form(None),
    text_model: str = Form(...),
    text_model_api_key: str | None = Form(None),
    image_processing_approach: ImageProcessingApproach = Form(...),
    user_settings: UserSettings = Depends(
        lambda: None
    ),  # placeholder will be refreshed after update
) -> HTMLResponse:
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
        image_model_provider=image_model_provider,
        image_model_base_url=image_model_base_url,
        image_model=image_model,
        text_model_provider=text_model_provider,
        text_model_base_url=text_model_base_url,
        text_model=text_model,
        image_processing_approach=image_processing_approach,
    )

    if any(
        [
            image_provider_error,
            image_base_url_error,
            image_model_error,
            image_api_key_error,
            text_provider_error,
            text_base_url_error,
            text_model_error,
            text_api_key_error,
        ]
    ):
        # Need fresh settings for page context
        async with get_db_connection() as conn:
            existing = await update_user_settings_query(
                conn, settings={}
            )  # no-op fetch
        page = await create_llm_models_page(
            user_settings=existing,
            image_provider_error=image_provider_error,
            image_base_url_error=image_base_url_error,
            image_model_error=image_model_error,
            image_api_key_error=image_api_key_error,
            text_provider_error=text_provider_error,
            text_base_url_error=text_base_url_error,
            text_model_error=text_model_error,
            text_api_key_error=text_api_key_error,
            image_provider_value=image_model_provider.value
            if image_model_provider
            else None,
            image_base_url_value=image_model_base_url,
            image_model_value=image_model,
            text_provider_value=text_model_provider.value
            if text_model_provider
            else None,
            text_base_url_value=text_model_base_url,
            text_model_value=text_model,
            image_processing_approach_value=image_processing_approach.value,
        )
        return HTMLResponse(content=page, status_code=status.HTTP_200_OK)

    if text_model_api_key:
        text_model_api_key_enc = encrypt_secret(
            text_model_api_key,
            config.master_key.get_secret_value(),
            aad=AADS.LLM_API_KEY,
        )
    else:
        text_model_api_key_enc = None
    if image_model_api_key:
        image_model_api_key_enc = encrypt_secret(
            image_model_api_key,
            config.master_key.get_secret_value(),
            aad=AADS.LLM_API_KEY,
        )
    else:
        image_model_api_key_enc = None

    settings_to_update = {
        "image_model_provider": image_model_provider.value,
        "image_model_base_url": image_model_base_url,
        "image_model": image_model,
        "image_model_api_key_enc": image_model_api_key_enc,
        "text_model_provider": text_model_provider.value,
        "text_model_base_url": text_model_base_url,
        "text_model": text_model,
        "text_model_api_key_enc": text_model_api_key_enc,
        "image_processing_approach": image_processing_approach.value,
    }

    async with get_db_connection() as conn:
        user_settings = await update_user_settings_query(
            conn, settings=settings_to_update
        )
    set_fn = getattr(central_cache, "set", None)
    if set_fn is not None:
        await set_fn("user_settings", user_settings, ttl=user_settings_ttl)
    response_page = await create_llm_models_page(user_settings=user_settings)
    response = HTMLResponse(content=response_page)
    response.headers["HX-Trigger"] = json.dumps(
        {
            "basecoat:toast": {
                "config": {
                    "category": "success",
                    "title": "Settings Saved",
                    "description": "Your LLM model settings have been updated.",
                }
            }
        }
    )
    return response


# Test endpoints kept here for cohesion


@router.get("/user-settings/test-model/text")
async def test_text_model(
    text_model_provider: ModelProvider,
    text_model_base_url: str | None = None,
    text_model: str | None = None,
    text_model_api_key: str | None = None,
    user_settings: UserSettings | None = Depends(get_user_settings_optional),
) -> HTMLResponse:
    form_provider = text_model_provider
    form_base_url = text_model_base_url or (
        None
        if user_settings is None
        else user_settings.text_model_config.model_base_url
    )
    form_model = text_model or (
        None if user_settings is None else user_settings.text_model_config.model
    )
    used_api_key_source = (
        "provided in form"
        if (text_model_api_key or "").strip()
        else (
            "none"
            if user_settings is None
            else (
                "saved in settings"
                if user_settings.text_model_config.api_key
                else "none"
            )
        )
    )
    effective_api_key = (
        (text_model_api_key or None)
        if (text_model_api_key or "").strip()
        else (
            None if user_settings is None else user_settings.text_model_config.api_key
        )
    )
    # Determine the correct provider class based on the model_provider string
    if form_provider == ModelProvider.GOOGLE_AI:
        eff_cfg = GoogleAIConfig(
            model_base_url=form_base_url,
            model=form_model or "",
            api_key=effective_api_key,
        )
    elif form_provider == ModelProvider.OPENAI:
        eff_cfg = OpenAIConfig(
            model_base_url=form_base_url,
            model=form_model or "",
            api_key=effective_api_key,
        )
    elif form_provider == ModelProvider.OPENAI_GENERIC:
        eff_cfg = OpenAIGenericConfig(
            model_base_url=form_base_url,
            model=form_model or "",
            api_key=effective_api_key,
        )
    elif form_provider == ModelProvider.ANTHROPIC:
        eff_cfg = AnthropicConfig(
            model_base_url=form_base_url,
            model=form_model or "",
            api_key=effective_api_key,
        )
    else:
        raise ValueError(f"Unknown text model provider: {form_provider}")
    cr = create_client_registry(llm_config=eff_cfg, name="TextClient", set_primary=True)
    rows = []
    structured_ok = False
    structured_err = None
    try:
        tag_catalog = [
            baml_types.Tag(name="Dog", description=""),
            baml_types.Tag(name="Cat", description=""),
            baml_types.Tag(name="Table", description=""),
        ]
        resp = await b.TextTestStructured(
            activity_name="Quick check",
            activity_description="A static object that people use for placing things.",
            tag_catalog=tag_catalog,
            baml_options={"client_registry": cr},
        )
        structured_ok = getattr(resp, "correct_choice", None) == "Table"
        if not structured_ok:
            structured_err = (
                f"Expected 'Table', got '{getattr(resp, 'correct_choice', None)}'"
            )
    except Exception as e:
        logger.exception("Text model structured test failed")
        structured_err = str(e)
    rows.append(("Structured", structured_ok, structured_err))
    unstructured_ok = False
    unstructured_err = None
    try:
        ans = await b.TextTestUnstructured(baml_options={"client_registry": cr})
        ans_norm = (ans or "").strip().lower()
        unstructured_ok = ans_norm == "dog"
        if not unstructured_ok:
            unstructured_err = f"Expected 'Dog', got '{ans}'"
    except Exception as e:
        logger.exception("Text model unstructured test failed")
        unstructured_err = str(e)
    rows.append(("Unstructured", unstructured_ok, unstructured_err))
    info = f"Auth: {used_api_key_source}"

    modal = build_llm_test_modal(
        title="Text Model Test",
        rows=rows,
        auth_info=info,
    )
    return HTMLResponse(content=modal)


@router.get("/user-settings/test-model/image")
async def test_image_model(
    image_model_provider: ModelProvider,
    image_model_base_url: str | None = None,
    image_model: str | None = None,
    image_model_api_key: str | None = None,
    user_settings: UserSettings | None = Depends(get_user_settings_optional),
) -> HTMLResponse:
    saved_image_config = (
        None if user_settings is None else user_settings.image_model_config
    )
    form_provider = image_model_provider
    form_base_url = image_model_base_url or (
        None if saved_image_config is None else saved_image_config.model_base_url
    )
    form_model = image_model or (
        None if saved_image_config is None else saved_image_config.model
    )
    used_api_key_source = (
        "provided in form"
        if (image_model_api_key or "").strip()
        else (
            "none"
            if user_settings is None
            else (
                "saved in settings"
                if (saved_image_config and saved_image_config.api_key)
                else "none"
            )
        )
    )
    effective_api_key = (
        (image_model_api_key or None)
        if (image_model_api_key or "").strip()
        else (None if saved_image_config is None else saved_image_config.api_key)
    )
    # Determine the correct provider class based on the model_provider string
    if form_provider == ModelProvider.GOOGLE_AI:
        eff_cfg = GoogleAIConfig(
            model_base_url=form_base_url,
            model=form_model or "",
            api_key=effective_api_key,
        )
    elif form_provider == ModelProvider.OPENAI:
        eff_cfg = OpenAIConfig(
            model_base_url=form_base_url,
            model=form_model or "",
            api_key=effective_api_key,
        )
    elif form_provider == ModelProvider.OPENAI_GENERIC:
        eff_cfg = OpenAIGenericConfig(
            model_base_url=form_base_url,
            model=form_model or "",
            api_key=effective_api_key,
        )
    elif form_provider == ModelProvider.ANTHROPIC:
        eff_cfg = AnthropicConfig(
            model_base_url=form_base_url,
            model=form_model or "",
            api_key=effective_api_key,
        )
    else:
        raise ValueError(f"Unknown image model provider: {form_provider}")
    cr = create_client_registry(
        llm_config=eff_cfg, name="ImageClient", set_primary=True
    )
    rows = []
    structured_ok = False
    structured_err = None
    try:
        resp = await b.ImageTestStructured(baml_options={"client_registry": cr})
        structured_ok = getattr(resp, "correct_choice", None) in {"Dog", "Cat", "Table"}
        if not structured_ok:
            structured_err = (
                f"Unexpected choice '{getattr(resp, 'correct_choice', None)}'"
            )
    except Exception as e:
        logger.exception("Image model structured test failed")
        structured_err = str(e)
    rows.append(("Structured", structured_ok, structured_err))
    unstructured_ok = False
    unstructured_err = None
    try:
        ans = await b.ImageTestUnstructured(baml_options={"client_registry": cr})
        ans_norm = (ans or "").strip().lower()
        unstructured_ok = ans_norm in {"car", "tree", "house"}
        if not unstructured_ok:
            unstructured_err = f"Expected one of Car/Tree/House, got '{ans}'"
    except Exception as e:
        logger.exception("Image model unstructured test failed")
        unstructured_err = str(e)
    rows.append(("Unstructured", unstructured_ok, unstructured_err))
    info = f"Auth: {used_api_key_source}"
    modal = build_llm_test_modal(
        title="Image Model Test",
        rows=rows,
        auth_info=info,
    )
    return HTMLResponse(content=modal)
