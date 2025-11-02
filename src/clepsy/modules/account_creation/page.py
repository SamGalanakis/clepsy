from zoneinfo import available_timezones

from htpy import Element, div, form, h2, p

# Import shared components
from clepsy.entities import ImageProcessingApproach, ModelProvider
from clepsy.frontend.components import (
    create_button,
    create_generic_modal,
    create_single_select,
    create_standard_content,
    create_text_area,
    create_text_input,
)
from clepsy.modules.user_settings.llm.component import create_llm_editor
from clepsy.modules.user_settings.tags.component import create_tags_editor
from clepsy.utils import txt


DEFAULT_PRODUCTIVITY_PROMPT = txt(
    "VERY_PRODUCTIVE:",
    "- Deep focus work on core outputs",
    "Examples: Implementing features, drafting reports, architectural design",
    "",
    "PRODUCTIVE:",
    "- Supporting work that enables delivery",
    "Examples: Code reviews, planning, reading docs",
    "",
    "NEUTRAL:",
    "- Routine communication and admin",
    "Examples: Email triage, daily standups, scheduling",
    "",
    "DISTRACTING:",
    "- Non-essential browsing or casual chat",
    "Examples: Social media scrolling, random web reading",
    "",
    "VERY_DISTRACTING:",
    "- Entertainment or unrelated activities",
    "Examples: Gaming, streaming videos, personal social feeds",
    join="\n",
)


def create_basics_page(
    *,
    username_error: str | None = None,
    timezone_error: str | None = None,
    username_value: str | None = None,
    timezone_value: str | None = None,
) -> Element:
    default_timezone = "UTC"

    return create_standard_content(
        user_settings=None,
        include_sidebar_toggle=False,
        content=div(class_="container mx-auto max-w-2xl px-4")[
            # Welcome header
            div(class_="card p-6 space-y-2 mb-4")[
                h2(class_="text-2xl font-semibold text-on-surface-strong")[
                    "Welcome to Clepsy"
                ],
                p(class_="text-on-surface-variant")[
                    "Let’s set up the basics. You can tweak everything later in Settings."
                ],
            ],
            form(
                element_id="wizard-basics-form",
                method="POST",
                **{
                    "hx-post": "/s/create-account/basics",
                    "hx-target": "#content",
                    "hx-swap": "outerHTML",
                },
            )[
                div(class_="card p-6 space-y-6")[
                    h2(class_="text-lg font-semibold text-on-surface-strong mb-4")[
                        "Basics"
                    ],
                    div(class_="grid gap-3")[
                        create_text_input(
                            element_id="username",
                            name="username",
                            attrs={"type": "text"},
                            value=username_value or "",
                            placeholder="Enter a username",
                            title="Username",
                            required=True,
                            valid_state=username_error is None,
                        ),
                        p(class_="text-destructive text-sm")[username_error]
                        if username_error
                        else None,
                    ],
                    # (Password removed; managed via user_auth)
                    div(class_="grid gap-3")[
                        create_single_select(
                            element_id="timezone",
                            include_search=True,
                            name="timezone",
                            placeholder_text="Select a timezone",
                            title="Timezone",
                            options={
                                tz: tz for tz in sorted(list(available_timezones()))
                            },
                            selected_val=(
                                None
                                if timezone_error
                                else (timezone_value or default_timezone)
                            ),
                        ),
                        p(class_="text-destructive text-sm")[timezone_error]
                        if timezone_error
                        else None,
                    ],
                ],
                div(class_="card p-4 flex-row justify-end items-center mt-4")[
                    create_button(
                        text="Next", variant="primary", attrs={"type": "submit"}
                    ),
                ],
            ],
        ],
    )


def create_productivity_page(
    *, productivity_prompt_value: str | None = None
) -> Element:
    return create_standard_content(
        include_sidebar_toggle=False,
        user_settings=None,
        content=div(class_="container mx-auto max-w-3xl px-4")[
            form(
                element_id="wizard-productivity-form",
                method="POST",
                **{
                    "hx-post": "/s/create-account/productivity",
                    "hx-target": "#content",
                    "hx-swap": "outerHTML",
                },
            )[
                div(class_="card p-6 space-y-6")[
                    h2(class_="text-lg font-semibold text-on-surface-strong mb-4")[
                        "Productivity prompt"
                    ],
                    create_text_area(
                        element_id="productivity-prompt",
                        name="productivity_prompt",
                        value=productivity_prompt_value or DEFAULT_PRODUCTIVITY_PROMPT,
                        placeholder="Enter the prompt for productivity analysis...",
                        title="Productivity Level Prompt",
                        rows=12,
                    ),
                    p(class_="text-xs text-on-surface-variant mt-1")[
                        "You can always change this later in Settings."
                    ],
                ],
                div(class_="card p-4 flex-row justify-between items-center mt-4")[
                    create_button(
                        text="Back",
                        variant="secondary",
                        attrs={
                            "type": "button",
                            "hx-get": "/s/create-account/basics",
                            "hx-target": "#content",
                            "hx-swap": "outerHTML",
                        },
                    ),
                    create_button(
                        text="Next", variant="primary", attrs={"type": "submit"}
                    ),
                ],
            ],
        ],
    )


def create_tags_page(*, initial_tags: list[dict] | None = None) -> Element:
    # Use the reusable tags editor. It posts tags_data JSON.
    initial = initial_tags or []
    editor = create_tags_editor(
        initial_tags=initial,
        post_url="/s/create-account/tags",
        primary_text="Next",
        back_url="/s/create-account/productivity",
        include_skip=True,
        hx_target="#content",
        hx_swap="outerHTML",
        title="Initial tags (optional)",
        subtitle="Define a few starter tags now or skip and add them later.",
    )
    return create_standard_content(
        user_settings=None,
        include_sidebar_toggle=False,
        content=div(class_="container mx-auto max-w-3xl px-4")[editor],
    )


def create_models_page(
    *,
    image_model_provider_value: str | None = None,
    image_model_base_url_value: str | None = None,
    image_model_value: str | None = None,
    text_model_provider_value: str | None = None,
    text_model_base_url_value: str | None = None,
    text_model_value: str | None = None,
    image_provider_error: str | None = None,
    image_base_url_error: str | None = None,
    image_model_error: str | None = None,
    image_api_key_error: str | None = None,
    text_provider_error: str | None = None,
    text_base_url_error: str | None = None,
    text_model_error: str | None = None,
    text_api_key_error: str | None = None,
    image_processing_approach_value: str | None = None,
) -> Element:
    valid_processing_values = {ap.value for ap in ImageProcessingApproach}
    editor = create_llm_editor(
        post_url="/s/create-account/models",
        initial_image_provider=image_model_provider_value
        or ModelProvider.GOOGLE_AI.value,
        initial_image_base_url=image_model_base_url_value or "",
        initial_image_model=image_model_value or "gemini-2.5-flash",
        initial_text_provider=text_model_provider_value
        or ModelProvider.GOOGLE_AI.value,
        initial_text_base_url=text_model_base_url_value or "",
        initial_text_model=text_model_value or "gemini-2.5-flash",
        initial_image_processing_approach=(
            image_processing_approach_value
            if image_processing_approach_value in valid_processing_values
            else ImageProcessingApproach.OCR.value
        ),
        image_provider_error=image_provider_error,
        image_base_url_error=image_base_url_error,
        image_model_error=image_model_error,
        image_api_key_error=image_api_key_error,
        text_provider_error=text_provider_error,
        text_base_url_error=text_base_url_error,
        text_model_error=text_model_error,
        text_api_key_error=text_api_key_error,
        primary_text="Finish",
        back_url="/s/create-account/tags",
        hx_target="#content",
        hx_swap="outerHTML",
        show_test_buttons=True,
    )
    return create_standard_content(
        user_settings=None,
        include_sidebar_toggle=False,
        content=div(class_="container mx-auto max-w-3xl px-4")[editor],
    )


def create_connect_page() -> Element:
    add_source_modal = create_generic_modal(
        modal_id="add-source-modal",
        content_id="add-source-modal-content",
        extra_classes="w-full sm:max-w-[425px]",
    )
    inner = div(class_="card min-w-[theme(screens.md)] w-fit mx-auto")[
        div(class_="p-6 border-b border-outline")[
            h2(class_="text-lg font-semibold text-on-surface-strong")[
                "Connect a source"
            ],
            p(class_="text-sm text-muted-foreground mt-1")[
                "Add a desktop device or other source to start sending data. You can also do this later from Settings → Sources."
            ],
        ],
        div(class_="px-6 py-4")[
            # Placeholder table area (will be filled by partial)
            div(
                id="sources-table",
                class_="mx-auto p-8 text-center text-muted-foreground",
            )["No sources yet — click Add source to pair your desktop app."],
            # Auto-load and refresh the table
            div(
                class_="hidden",
                **{
                    "hx-get": "/s/user-settings/sources/table",
                    "hx-trigger": "load, every 10s",
                    "hx-target": "#sources-table",
                    "hx-swap": "outerHTML",
                },
            ),
        ],
        div(
            class_="p-4 flex justify-between items-center bg-surface-subtle rounded-b-lg"
        )[
            create_button(
                text="Finish setup",
                variant="secondary",
                attrs={
                    "type": "button",
                    "hx-post": "/s/create-account/connect/finish",
                    "hx-target": "#content",
                    "hx-swap": "outerHTML",
                },
            ),
            create_button(
                text="Add source",
                variant="primary",
                attrs={
                    "type": "button",
                    "hx-get": "/s/add-source-modal",
                    "hx-target": "#add-source-modal-content",
                    "hx-swap": "innerHTML",
                    "onclick": "document.getElementById('add-source-modal').showModal()",
                },
            ),
        ],
        add_source_modal,
    ]
    return create_standard_content(
        user_settings=None,
        include_sidebar_toggle=False,
        content=div(class_="container mx-auto max-w-3xl px-4")[inner],
    )
