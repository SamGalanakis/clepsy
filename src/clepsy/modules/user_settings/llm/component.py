from __future__ import annotations

from htpy import Element, div, form, h2, input as htpy_input, label, p, span

from clepsy.entities import ImageProcessingApproach, ModelProvider
from clepsy.frontend.components import (
    create_button,
    create_generic_modal,
    create_single_select,
    create_text_input,
)
from clepsy.frontend.components.icons import get_icon_svg


def create_llm_editor(
    *,
    post_url: str,
    # initial values
    initial_image_provider: str | None = None,
    initial_image_base_url: str | None = None,
    initial_image_model: str | None = None,
    initial_text_provider: str | None = None,
    initial_text_base_url: str | None = None,
    initial_text_model: str | None = None,
    initial_image_processing_approach: str | None = None,
    # errors
    image_provider_error: str | None = None,
    image_base_url_error: str | None = None,
    image_model_error: str | None = None,
    image_api_key_error: str | None = None,
    text_provider_error: str | None = None,
    text_base_url_error: str | None = None,
    text_model_error: str | None = None,
    text_api_key_error: str | None = None,
    # controls
    primary_text: str = "Save",
    back_url: str | None = None,
    cancel_url: str | None = None,
    hx_target: str = "#content",
    hx_swap: str = "outerHTML",
    show_test_buttons: bool = False,
) -> Element:
    provider_options = {
        name.capitalize(): m.value for name, m in ModelProvider.__members__.items()
    }

    selected_approach = (
        initial_image_processing_approach
        if initial_image_processing_approach is not None
        else ImageProcessingApproach.OCR.value
    )
    vlm_value = ImageProcessingApproach.VLM.value

    image_modal_body_id = "test-image-model-modal-body"
    image_spinner_id = "test-image-model-modal-spinner"
    text_modal_body_id = "test-text-model-modal-body"
    text_spinner_id = "test-text-model-modal-spinner"

    def _approach_card(
        approach: ImageProcessingApproach, title: str, description: str
    ) -> Element:
        base_classes = (
            "relative flex gap-3 rounded-lg border p-4 cursor-pointer transition"
        )
        selected_classes = "border-primary ring-2 ring-primary/30 bg-primary/5"
        unselected_classes = "border-outline hover:border-primary bg-surface"

        is_selected = selected_approach == approach.value

        return label(
            class_=base_classes,
            **{
                "x-bind:class": (
                    f"selectedApproach === '{approach.value}' ? '{selected_classes}' : '{unselected_classes}'"
                ),
            },
        )[
            htpy_input(
                type="radio",
                name="image_processing_approach",
                value=approach.value,
                checked=is_selected,
                class_="mt-1 h-4 w-4",
                **{"x-on:change": "selectedApproach = $event.target.value"},
            ),
            div(class_="space-y-1")[
                span(class_="font-medium text-on-surface-strong")[title],
                p(class_="text-sm text-muted-foreground")[description],
            ],
        ]

    # Main form content
    form_inner = div(class_="card p-6 space-y-6")[
        div(class_="space-y-3")[
            h2(class_="text-lg font-semibold text-on-surface-strong")[
                "Screenshot processing"
            ],
            p(class_="text-sm text-muted-foreground")[
                "Choose how Clepsy interprets desktop screenshots before tagging activities."
            ],
            div(class_="grid gap-3 sm:grid-cols-2")[
                _approach_card(
                    ImageProcessingApproach.OCR,
                    "OCR (faster, text-only)",
                    "Extract text locally with OCR. Great when on-screen text provides sufficient context. Avoids sending images to external provider if not using self-hosted models.",
                ),
                _approach_card(
                    ImageProcessingApproach.VLM,
                    "Vision-Language model (richer context)",
                    "Send full screenshots to your configured vision model for more context-aware summaries. Make sure you trust your model provider with your screenshots.",
                ),
            ],
        ],
        # Image model
        div(
            **{
                "x-show": f"selectedApproach === '{vlm_value}'",
                "x-cloak": True,
                "x-transition.opacity": "",
            }
        )[
            div(class_="flex items-center justify-between mb-4")[
                h2(class_="text-lg font-semibold text-on-surface-strong")[
                    "Image Model"
                ],
                (
                    create_button(
                        text="Test",
                        variant="secondary",
                        size="sm",
                        attrs={
                            "type": "button",
                            "hx-get": "/s/user-settings/test-model/image",
                            "hx-indicator": f"#{image_spinner_id}",
                            "hx-vals": (
                                "js:{ image_model_provider: document.getElementById('image-model-provider-hidden-input').value,"
                                " image_model_base_url: document.getElementById('image-model-base-url').value,"
                                " image_model: document.getElementById('image-model').value,"
                                " image_model_api_key: document.getElementById('image-model-api-key').value }"
                            ),
                            "hx-target": f"#{image_modal_body_id}",
                            "hx-swap": "innerHTML",
                            "onclick": "document.getElementById('test-image-model-modal').showModal()",
                        },
                    )
                    if show_test_buttons
                    else None
                ),
            ],
            create_single_select(
                element_id="image-model-provider",
                name="image_model_provider",
                title="Model Provider",
                placeholder_text="Select a provider",
                options=provider_options,
                selected_val=initial_image_provider,
            ),
            p(class_="text-destructive text-sm")[image_provider_error]
            if image_provider_error
            else None,
            create_text_input(
                title="Base URL (Optional)",
                element_id="image-model-base-url",
                name="image_model_base_url",
                value=initial_image_base_url or "",
                placeholder="https://api.example.com/v1",
                description="Leave blank for default.",
                extra_classes="mt-4",
                valid_state=image_base_url_error is None,
                attrs={"type": "url"},
            ),
            p(class_="text-destructive text-sm")[image_base_url_error]
            if image_base_url_error
            else None,
            create_text_input(
                title="Model Name",
                element_id="image-model",
                name="image_model",
                value=initial_image_model or "",
                placeholder="gpt-4-vision-preview",
                extra_classes="mt-4",
                valid_state=image_model_error is None,
                attrs={
                    "type": "text",
                    "x-bind:required": f"selectedApproach === '{vlm_value}'",
                },
            ),
            p(class_="text-destructive text-sm")[image_model_error]
            if image_model_error
            else None,
            create_text_input(
                element_id="image-model-api-key",
                name="image_model_api_key",
                value="",
                placeholder="sk-...",
                title="API Key",
                description="Your image model API key.",
                extra_classes="mt-4",
                valid_state=image_api_key_error is None,
                attrs={"type": "password"},
            ),
            p(class_="text-destructive text-sm")[image_api_key_error]
            if image_api_key_error
            else None,
        ],
        # Text model
        div(class_="pt-6 border-t border-outline")[
            div(class_="flex items-center justify-between mb-4")[
                h2(class_="text-lg font-semibold text-on-surface-strong")["Text Model"],
                (
                    create_button(
                        text="Test",
                        variant="secondary",
                        size="sm",
                        attrs={
                            "type": "button",
                            "hx-get": "/s/user-settings/test-model/text",
                            "hx-indicator": f"#{text_spinner_id}",
                            "hx-vals": (
                                "js:{ text_model_provider: document.getElementById('text-model-provider-hidden-input').value,"
                                " text_model_base_url: document.getElementById('text-model-base-url').value,"
                                " text_model: document.getElementById('text-model').value,"
                                " text_model_api_key: document.getElementById('text-model-api-key').value }"
                            ),
                            "hx-target": f"#{text_modal_body_id}",
                            "hx-swap": "innerHTML",
                            "onclick": "document.getElementById('test-text-model-modal').showModal()",
                        },
                    )
                    if show_test_buttons
                    else None
                ),
            ],
            create_single_select(
                element_id="text-model-provider",
                name="text_model_provider",
                title="Model Provider",
                placeholder_text="Select a provider",
                options=provider_options,
                selected_val=initial_text_provider,
            ),
            p(class_="text-destructive text-sm")[text_provider_error]
            if text_provider_error
            else None,
            create_text_input(
                title="Base URL (Optional)",
                element_id="text-model-base-url",
                name="text_model_base_url",
                attrs={"type": "url"},
                value=initial_text_base_url or "",
                placeholder="https://api.example.com/v1",
                description="Leave blank for default.",
                extra_classes="mt-4",
                valid_state=text_base_url_error is None,
            ),
            p(class_="text-destructive text-sm")[text_base_url_error]
            if text_base_url_error
            else None,
            create_text_input(
                title="Model Name",
                element_id="text-model",
                name="text_model",
                value=initial_text_model or "",
                placeholder="gpt-4-turbo",
                attrs={"type": "text"},
                extra_classes="mt-4",
                valid_state=text_model_error is None,
            ),
            p(class_="text-destructive text-sm")[text_model_error]
            if text_model_error
            else None,
            create_text_input(
                element_id="text-model-api-key",
                name="text_model_api_key",
                value="",
                placeholder="sk-...",
                title="API Key",
                attrs={"type": "password"},
                description="Your text model API key.",
                extra_classes="mt-4",
                valid_state=text_api_key_error is None,
            ),
            p(class_="text-destructive text-sm")[text_api_key_error]
            if text_api_key_error
            else None,
        ],
    ]

    # Wrap in a form with actions
    actions = div(class_="card p-4 flex-row justify-between items-center mt-4")[
        (
            create_button(
                text="Back",
                variant="secondary",
                attrs={
                    "type": "button",
                    "hx-get": back_url,
                    "hx-target": hx_target,
                    "hx-swap": hx_swap,
                },
            )
            if back_url
            else None
        ),
        div(class_="flex items-center gap-3")[
            (
                create_button(
                    text="Cancel",
                    variant="destructive",
                    attrs={
                        "type": "button",
                        "hx-get": cancel_url,
                        "hx-target": hx_target,
                        "hx-swap": hx_swap,
                    },
                )
                if cancel_url
                else None
            ),
            create_button(
                text=primary_text, variant="primary", attrs={"type": "submit"}
            ),
        ],
    ]

    content = [form_inner, actions]

    # Optional test modals
    if show_test_buttons:
        spinner_icon = get_icon_svg("rotate_cw")

        def _modal_children(body_id: str, spinner_id: str) -> Element:
            return div(class_="relative min-h-24")[
                div(id=body_id),
                div(
                    id=spinner_id,
                    class_=(
                        "htmx-indicator absolute inset-0 flex items-center justify-center "
                        "bg-surface/70 pointer-events-none z-10"
                    ),
                )[
                    div(class_="p-4 flex items-center gap-3 bg-surface rounded shadow")[
                        div(class_="animate-spin text-muted-foreground")[spinner_icon],
                        p(class_="text-sm text-muted-foreground")["Testing model…"],
                    ]
                ],
            ]

        content.extend(
            [
                create_generic_modal(
                    modal_id="test-image-model-modal",
                    content_id="test-image-model-modal-content",
                    children=_modal_children(image_modal_body_id, image_spinner_id),
                    extra_classes="w-full max-w-[90vw] sm:max-w-lg",
                ),
                create_generic_modal(
                    modal_id="test-text-model-modal",
                    content_id="test-text-model-modal-content",
                    children=_modal_children(text_modal_body_id, text_spinner_id),
                    extra_classes="w-full max-w-[90vw] sm:max-w-lg",
                ),
            ]
        )

    x_data = f"{{selectedApproach: '{selected_approach}'}}"
    x_init = (
        "(() => {"
        " const checked = document.querySelector(\"input[name='image_processing_approach']:checked\");"
        " if (checked) { selectedApproach = checked.value; }"
        " })()"
    )

    return form(
        element_id="llm-models-form",
        method="POST",
        x_data=x_data,
        x_init=x_init,
        **{"hx-post": post_url, "hx-target": hx_target, "hx-swap": hx_swap},
    )[content]
