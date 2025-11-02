from htpy import Element, div, form, h2, p

from clepsy.entities import UserSettings
from clepsy.frontend.components import (
    common_timezones_list,
    create_button,
    create_single_select,
    create_standard_content,
    create_text_input,
)


async def create_general_settings_page(
    user_settings: UserSettings,
    username_error: str | None = None,
    timezone_error: str | None = None,
    username_value: str | None = None,
    timezone_value: str | None = None,
) -> Element:
    form_inner_content = div(class_="card p-6 space-y-6")[
        h2(class_="text-lg font-semibold text-on-surface-strong mb-4")["General"],
        div(class_="grid gap-3 mt-4")[
            create_text_input(
                element_id="username",
                name="username",
                attrs={"type": "text"},
                value=(
                    (username_value or "")
                    if username_error is None and username_value is not None
                    else (username_value or "")
                ),
                placeholder="Enter a username",
                title="Username",
                valid_state=username_error is None,
            ),
            p(class_="text-destructive text-sm")[username_error]
            if username_error
            else None,
        ],
        div(class_="grid gap-3 mt-2")[
            create_single_select(
                element_id="timezone",
                include_search=True,
                name="timezone",
                placeholder_text="Select a timezone",
                title="Timezone",
                options={tz: tz for tz in common_timezones_list},
                selected_val=(None if timezone_error else timezone_value),
            ),
            p(class_="text-destructive text-sm")[timezone_error]
            if timezone_error
            else None,
        ],
    ]

    form_with_buttons = form(
        element_id="general-settings-form",
        method="POST",
        **{
            "hx-post": "/s/user-settings/general",
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
                    "hx-get": "/s/user-settings/general",
                    "hx-target": "#content",
                    "hx-swap": "outerHTML",
                    "type": "button",
                },
            ),
            create_button(
                text="Save Changes",
                variant="primary",
                attrs={"type": "submit"},
                extra_classes="ml-3",
            ),
        ],
    ]

    return create_standard_content(
        user_settings=user_settings, content=[form_with_buttons]
    )
