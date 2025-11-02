from htpy import (
    Element,
    button,
    circle,
    div,
    header,
    option,
    path,
    script,
    select,
    span,
    svg,
)

from clepsy.entities import UserSettings

from .buttons import create_button
from .generic_modal import create_generic_modal


def create_dark_mode_switcher(attrs: dict | None = None):
    attrs = attrs or {}
    user_class = attrs.pop("class", "") or attrs.pop("class_", "") if attrs else ""
    return button(
        type="button",
        aria_label="Toggle dark mode",
        data_tooltip="Toggle dark mode",
        data_side="bottom",
        onclick="document.dispatchEvent(new CustomEvent('basecoat:theme'))",
        class_=("btn-icon-outline size-8 " + user_class).strip(),
        **attrs,
    )[
        span(class_="hidden dark:block")[
            svg(
                xmlns="http://www.w3.org/2000/svg",
                width="24",
                height="24",
                viewBox="0 0 24 24",
                fill="none",
                stroke="currentColor",
                stroke_width="2",
                stroke_linecap="round",
                stroke_linejoin="round",
            )[
                circle(cx="12", cy="12", r="4"),
                path(d="M12 2v2"),
                path(d="M12 20v2"),
                path(d="m4.93 4.93 1.41 1.41"),
                path(d="m17.66 17.66 1.41 1.41"),
                path(d="M2 12h2"),
                path(d="M20 12h2"),
                path(d="m6.34 17.66-1.41 1.41"),
                path(d="m19.07 4.93-1.41 1.41"),
            ]
        ],
        span(class_="block dark:hidden")[
            svg(
                xmlns="http://www.w3.org/2000/svg",
                width="24",
                height="24",
                viewBox="0 0 24 24",
                fill="none",
                stroke="currentColor",
                stroke_width="2",
                stroke_linecap="round",
                stroke_linejoin="round",
            )[path(d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z")]
        ],
    ]


def create_theme_switcher(attrs: dict | None = None):
    attrs = attrs or {}
    user_class = attrs.pop("class", "") or attrs.pop("class_", "") if attrs else ""
    return select(
        id="theme-select",
        class_=("select h-8 leading-none " + user_class).strip(),
        **attrs,
    )[
        option(value="default", selected=False)["Default"],
        option(value="catppuccin", selected=False)["Catppuccin"],
        option(value="modern_minimal", selected=False)["Modern minimal"],
    ]


def create_top_bar(
    user_settings: UserSettings | None,
    include_sidebar_toggle: bool = True,
    include_add_activity: bool = True,
) -> Element:
    is_logged_in = user_settings is not None

    # --- widgets ------------------------------------------------------------
    theme_switcher = create_theme_switcher()
    dark_mode_switcher = create_dark_mode_switcher()
    logout_button = create_button(
        variant="link",
        text="Logout",
        attrs={"onclick": "window.location.href='/s/logout'"},
    )
    add_activity_button = create_button(
        text=None,
        icon="plus",
        variant="outline",
        size="default",
        extra_classes="size-8",
        attrs={
            "data-tooltip": "Add activity",
            "data-side": "bottom",
            # Load modal content like the home page button
            "hx-get": "/s/activities/add-activity-modal",
            "hx-target": "#add-activity-modal-content",
            "hx-swap": "innerHTML",
            # Show the modal only if present on this page
            "onclick": "var m=document.getElementById('add-activity-modal'); if(m){m.showModal()}",
            "aria-label": "Add activity",
        },
    )
    sidebar_toggle = create_button(
        text=None,
        icon="sidebar_toggle",
        variant="ghost",
        extra_classes="size-7 -ml-1.5",  # ← removed mr-auto
        attrs={
            "onclick": "document.dispatchEvent(new CustomEvent('basecoat:sidebar'))",
            "data-side": "bottom",
            "data-align": "start",
            "data-tooltip": "Toggle sidebar",
            "aria-label": "Toggle sidebar",
        },
    )

    # --- layout -------------------------------------------------------------
    header_el = header(
        class_="bg-background sticky inset-x-0 top-0 isolate flex shrink-0 items-center border-b z-10"
    )[
        div(class_="flex h-14 w-full items-center px-4")[
            # left side ------------------------------------------------------
            sidebar_toggle if include_sidebar_toggle else None,
            # right side (ml-auto pushes this group to the far right) --------
            div(class_="ml-auto flex items-center gap-2")[
                add_activity_button if include_add_activity else None,
                theme_switcher,
                script(src="/static/custom_scripts/theme_switcher.js"),
                dark_mode_switcher,
                script(src="/static/custom_scripts/dark_light_mode.js"),
                logout_button if is_logged_in else None,
            ],
        ]
    ]

    # Optionally include the Add Activity modal globally within the header context
    if include_add_activity:
        return div()[
            header_el,
            create_generic_modal(
                modal_id="add-activity-modal",
                content_id="add-activity-modal-content",
                extra_classes="w-[92vw] sm:max-w-[480px] md:max-w-[560px] lg:max-w-[640px] xl:max-w-[720px]",
            ),
        ]
    return header_el
