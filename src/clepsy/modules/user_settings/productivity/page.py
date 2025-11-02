from htpy import Element, div, form, h2

from clepsy.entities import UserSettings
from clepsy.frontend.components import (
    create_button,
    create_markdown_editor,
    create_standard_content,
)


async def create_productivity_page(user_settings: UserSettings) -> Element:
    form_inner_content = div(class_="card p-6 space-y-6")[
        h2(class_="text-lg font-semibold text-on-surface-strong mb-4")["Productivity"],
        create_markdown_editor(
            element_id="productivity-prompt",
            name="productivity_prompt",
            value=user_settings.productivity_prompt or "",
            placeholder="e.g., How productive was I...",
            title="Productivity Level Prompt",
            height="150px",
        ),
    ]
    form_with_buttons = form(
        element_id="productivity-form",
        method="POST",
        **{
            "hx-post": "/s/user-settings/productivity",
            "hx-target": "#content",
            "hx-swap": "outerHTML",
        },
    )[
        form_inner_content,
        div(class_="card p-4 flex-row justify-around items-center mt-4")[
            create_button(
                text="Cancel",
                variant="destructive",
                attrs={
                    "hx-get": "/s/user-settings/productivity",
                    "hx-target": "#content",
                    "hx-swap": "outerHTML",
                },
            ),
            create_button(
                text="Save",
                variant="primary",
                attrs={"type": "submit"},
                extra_classes="ml-3",
            ),
        ],
    ]
    return create_standard_content(
        user_settings=user_settings, content=[form_with_buttons]
    )
