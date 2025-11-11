from htpy import Element, div, form, h2, p

from clepsy.entities import UserSettings
from clepsy.frontend.components import (
    create_button,
    create_standard_content,
    create_text_input,
)


async def create_password_page(
    user_settings: UserSettings,
    current_password_error: str | None = None,
    new_password_error: str | None = None,
    confirm_password_error: str | None = None,
    new_password_value: str | None = None,
    confirm_password_value: str | None = None,
) -> Element:
    form_inner_content = div(class_="card p-6 space-y-6")[
        h2(class_="text-lg font-semibold text-on-surface-strong mb-4")[
            "Change Password"
        ],
        div(class_="grid gap-3")[
            create_text_input(
                element_id="current-password",
                name="current_password",
                required=True,
                value="",
                title="Current Password",
                attrs={"type": "password"},
                valid_state=current_password_error is None,
            ),
            p(class_="text-destructive text-sm")[current_password_error]
            if current_password_error
            else None,
        ],
        div(class_="grid gap-3")[
            create_text_input(
                element_id="new-password-change",
                name="new_password",
                required=True,
                value=new_password_value
                if new_password_error is None and new_password_value is not None
                else "",
                title="New Password",
                attrs={"type": "password"},
                valid_state=new_password_error is None,
            ),
            p(class_="text-destructive text-sm")[new_password_error]
            if new_password_error
            else None,
        ],
        div(class_="grid gap-3")[
            create_text_input(
                element_id="confirm-password",
                name="confirm_password",
                required=True,
                value=confirm_password_value
                if confirm_password_error is None and confirm_password_value is not None
                else "",
                title="Confirm New Password",
                attrs={"type": "password"},
                valid_state=confirm_password_error is None,
            ),
            p(class_="text-destructive text-sm")[confirm_password_error]
            if confirm_password_error
            else None,
        ],
    ]

    form_with_buttons = form(
        element_id="password-change-form",
        method="POST",
        **{
            "hx-post": "/s/change-password",
            "hx-target": "#content",
            "hx-swap": "outerHTML",
        },
    )[
        form_inner_content,
        div(class_="card p-4 flex-row justify-center items-center mt-4")[
            create_button(text="Submit", variant="primary", attrs={"type": "submit"}),
        ],
    ]

    return create_standard_content(
        user_settings=user_settings, content=[form_with_buttons]
    )
