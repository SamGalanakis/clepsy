from typing import Any

from htpy import (
    Element,
    a,
    aside,
    details,
    div,
    header,
    li,
    nav,
    section,
    span,
    summary,
    ul,
)

from clepsy.frontend.components.icons import get_icon_svg


def create_custom_sidebar(
    attrs: dict[str, Any] | None = None,
) -> Element:
    """Creates a custom sidebar component."""
    if attrs is None:
        attrs = {}
    user_class = attrs.pop("class", "") or attrs.pop("class_", "") if attrs else ""

    aside_attrs = {
        "data-side": "left",
        "aria-hidden": "false",
        **attrs,
    }

    settings_svg = get_icon_svg("settings")

    settings_items = {
        "General": "/s/user-settings/general",
        "Password": "/s/user-settings/password",
        "LLM Models": "/s/user-settings/llm_models",
        "Tags": "/s/user-settings/tags",
        "Productivity": "/s/user-settings/productivity",
        "Sources": "/s/user-settings/sources",
    }

    return aside(class_=("sidebar " + user_class).strip(), **aside_attrs)[
        nav(aria_label="Sidebar navigation")[
            header[
                a(
                    href="/s",
                    class_=(
                        "group flex items-center gap-3 w-full h-14 px-3 rounded-md "
                        "font-semibold text-lg tracking-wide leading-none select-none "
                        "border-l-4 border-transparent hover:border-primary transition-colors "
                        "hover:bg-accent/50 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    ),
                )[
                    get_icon_svg("clepsy_logo"),
                    span(class_="group-hover:text-primary transition-colors")["Clepsy"],
                ]
            ],
            # Divider
            div(class_="h-px w-full bg-border my-2"),
            section(class_="scrollbar")[
                div(role="group", aria_labelledby="group-label-content-1")[
                    ul[
                        li[
                            a(
                                href="/s/goals",
                                hx_boost=True,
                                hx_target="#content",
                                hx_swap="outerHTML",
                            )[
                                get_icon_svg("goal"),
                                span["Goals"],
                            ]
                        ],
                        li[
                            a(
                                href="/s/insights",
                                hx_boost=True,
                                hx_target="#content",
                                hx_swap="outerHTML",
                            )[
                                get_icon_svg("chart-column"),
                                span["Insights"],
                            ]
                        ],
                        li[
                            details(id="submenu-monitoring")[
                                summary(aria_controls="submenu-monitoring-content")[
                                    get_icon_svg("pulse"),
                                    "Monitoring",
                                ],
                                ul(id="submenu-monitoring-content")[
                                    li[
                                        a(
                                            href="/s/monitoring/workers",
                                            hx_boost=True,
                                            hx_target="#content",
                                            hx_swap="outerHTML",
                                        )[
                                            get_icon_svg("pickaxe"),
                                            span["Workers"],
                                        ]
                                    ]
                                ],
                            ]
                        ],
                        li[
                            details(id="submenu-settings")[
                                summary(aria_controls="submenu-settings-content")[
                                    settings_svg, "Settings"
                                ],
                                ul(id="submenu-settings-content")[
                                    [
                                        li[
                                            a(
                                                href=href,
                                                hx_boost=True,
                                                hx_target="#content",
                                                hx_swap="outerHTML",
                                            )[span[label]]
                                        ]
                                        for label, href in settings_items.items()
                                    ]
                                ],
                            ]
                        ],
                    ],
                ]
            ],
        ]
    ]
