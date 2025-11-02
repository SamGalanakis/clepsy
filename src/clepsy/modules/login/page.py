from typing import Optional

from htpy import Element, div, footer, form, h2, header, main, section
from loguru import logger

from clepsy.frontend.components import (
    create_button,
    create_text_input,
    create_top_bar,
)


def create_login_page(error_message: Optional[str] = None) -> Element:
    logger.trace("Creating login form")

    content = div(class_="card w-full max-w-sm")[
        header[h2["Login"]],
        section[
            form(
                id="login-form",
                class_="grid gap-6 form",
                method="POST",
                **{
                    "hx-post": "/s/login",
                    "hx-target": "#content",
                    "hx-swap": "outerHTML",
                },
            )[
                create_text_input(
                    element_id="password",
                    name="password",
                    title="Password",
                    placeholder="Enter your password",
                    required=True,
                    attrs={"type": "password"},
                ),
            ],
            footer(class_="flex flex-col items-center gap-2 mt-6")[
                create_button(
                    variant="primary",
                    text="Login",
                    extra_classes="w-full",
                    attrs={"type": "submit"},
                ),
            ],
        ],
    ]

    return main("#content")[
        create_top_bar(user_settings=None, include_sidebar_toggle=False),
        div(class_="p-4 md:p-6 xl:p-12")[
            # div(".mx-auto.w-full.flex-1.max-w-screen-md")[content],
            div(".flex.justify-center")[content]
        ],
    ]
