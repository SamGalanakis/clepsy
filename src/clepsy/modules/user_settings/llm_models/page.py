from htpy import (
    Element,
    div,
    h2,
    p,
    span,
    table,
    tbody,
    td,
    th,
    thead,
    tr,
)

from clepsy.entities import ImageProcessingApproach, ModelProvider, UserSettings
from clepsy.frontend.components import (
    create_button,
    create_standard_content,
)
from clepsy.frontend.components.icons import get_icon_svg
from clepsy.modules.user_settings.llm.component import create_llm_editor


async def create_llm_models_page(
    user_settings: UserSettings,
    image_provider_error: str | None = None,
    image_base_url_error: str | None = None,
    image_model_error: str | None = None,
    image_api_key_error: str | None = None,
    text_provider_error: str | None = None,
    text_base_url_error: str | None = None,
    text_model_error: str | None = None,
    text_api_key_error: str | None = None,
    image_provider_value: str | None = None,
    image_base_url_value: str | None = None,
    image_model_value: str | None = None,
    text_provider_value: str | None = None,
    text_base_url_value: str | None = None,
    text_model_value: str | None = None,
    image_processing_approach_value: str | None = None,
) -> Element:
    image_config = user_settings.image_model_config
    text_config = user_settings.text_model_config

    default_image_provider = (
        image_config.model_provider
        if image_config is not None
        else ModelProvider.GOOGLE_AI.value
    )
    default_text_provider = (
        text_config.model_provider
        if text_config is not None
        else ModelProvider.GOOGLE_AI.value
    )

    initial_image_provider = (
        image_provider_value
        if image_provider_value is not None and image_provider_error is None
        else default_image_provider
    )
    initial_image_base_url = (
        image_base_url_value
        if image_base_url_value is not None and image_base_url_error is None
        else (image_config.model_base_url if image_config else None)
    )
    initial_image_model = (
        image_model_value
        if image_model_value is not None and image_model_error is None
        else (image_config.model if image_config else "")
    )

    initial_text_provider = (
        text_provider_value
        if text_provider_value is not None and text_provider_error is None
        else default_text_provider
    )
    initial_text_base_url = (
        text_base_url_value
        if text_base_url_value is not None and text_base_url_error is None
        else (text_config.model_base_url if text_config else None)
    )
    initial_text_model = (
        text_model_value
        if text_model_value is not None and text_model_error is None
        else (text_config.model if text_config else "")
    )

    processing_fallback = (
        user_settings.image_processing_approach.value
        if getattr(user_settings, "image_processing_approach", None) is not None
        else ImageProcessingApproach.OCR.value
    )
    initial_processing = image_processing_approach_value or processing_fallback

    editor = create_llm_editor(
        post_url="/s/user-settings/llm_models",
        initial_image_provider=initial_image_provider,
        initial_image_base_url=initial_image_base_url,
        initial_image_model=initial_image_model,
        initial_text_provider=initial_text_provider,
        initial_text_base_url=initial_text_base_url,
        initial_text_model=initial_text_model,
        initial_image_processing_approach=initial_processing,
        image_provider_error=image_provider_error,
        image_base_url_error=image_base_url_error,
        image_model_error=image_model_error,
        image_api_key_error=image_api_key_error,
        text_provider_error=text_provider_error,
        text_base_url_error=text_base_url_error,
        text_model_error=text_model_error,
        text_api_key_error=text_api_key_error,
        primary_text="Save",
        cancel_url="/s/user-settings/llm_models",
        hx_target="#content",
        hx_swap="outerHTML",
        show_test_buttons=True,
    )

    return create_standard_content(
        user_settings=user_settings,
        content=[editor],
    )


# --- Helpers for building test result modals (moved from router) ---


def _status_cell(ok: bool) -> Element:
    return td(class_="p-3 align-top")[
        div(class_=("text-green-600" if ok else "text-red-600") + " flex items-center")[
            get_icon_svg("tick" if ok else "x")
        ]
    ]


def build_llm_test_modal(
    *,
    title: str,
    rows: list[tuple[str, bool, str | None]],
    auth_info: str,
) -> Element:
    """Return the inner content (no <dialog>) for a model test modal.

    Parameters
    ----------
    title: Title displayed in header.
    rows: Sequence of (label, ok, error_message_or_none).
    auth_info: A short string like "Auth: provided in form" or
      "Auth: saved in settings" used for info/warning banner.
    """
    header = div(
        class_="p-4 border-b border-outline flex items-center justify-between"
    )[
        h2(class_="text-lg font-semibold text-on-surface-strong")[title],
        create_button(
            text=None,
            icon="x",
            variant="secondary",
            attrs={"type": "button", "onclick": "this.closest('dialog').close()"},
        ),
    ]

    body_rows = [
        tr(class_="border-b last:border-0 border-outline align-top")[
            td(class_="p-3 text-on-surface-strong align-top")[label],
            _status_cell(ok),
            td(class_="p-3 align-top min-w-0")[
                div(
                    class_="w-full min-w-0 max-w-full text-sm text-muted-foreground max-h-40 overflow-y-auto overflow-x-hidden whitespace-pre-wrap break-words break-all pr-1"
                )[err or ""]
            ],
        ]
        for (label, ok, err) in rows
    ]

    body_children: list[Element | str] = [
        table(class_="w-full text-sm table-fixed")[
            thead(class_="text-left text-muted-foreground")[
                tr[
                    th(class_="p-3 w-28")["Test"],
                    th(class_="p-3 w-14")["Status"],
                    th(class_="p-3 w-auto")["Details"],
                ]
            ],
            tbody[body_rows],
        ],
        p(class_="text-xs text-muted-foreground mt-3")[
            "These checks call the configured model(s) with tiny prompts to validate connectivity and parsing."
        ],
    ]
    info_lower = auth_info.lower()
    if "saved in settings" in info_lower:
        body_children.insert(
            0,
            div(
                class_="mb-2 flex items-start gap-2 px-2 py-1 rounded bg-amber-50 text-amber-900 dark:bg-amber-900/20 dark:text-amber-300"
            )[
                get_icon_svg("warning"),
                div(class_="text-sm")[
                    span(class_="font-medium")[
                        "Auth: using API key saved in settings as none was provided in the form. To test with a different key, enter an API key in the form and click Test."
                    ],
                ],
            ],
        )
    else:
        body_children.insert(
            0, p(class_="text-sm text-muted-foreground mb-2")[auth_info]
        )

    body = div(class_="p-4")[body_children]
    return div(class_="bg-surface rounded-lg shadow-lg")[header, body]
