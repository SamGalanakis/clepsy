from htpy import Element, body, div, head, html, link, main, script, title

from clepsy.entities import UserSettings
from clepsy.frontend.components.sidebar import (
    create_custom_sidebar,
)
from clepsy.frontend.components.top_bar import create_top_bar

from .toasts import create_toaster_container


def create_standard_content(
    user_settings: UserSettings | None,
    content: Element | list[Element],
    outer_classes: str = "p-4 md:p-6 xl:p-12",
    inner_classes: str = "mx-auto w-full flex-1 max-w-screen-md",
    include_top_bar: bool = True,
    include_sidebar_toggle: bool = True,
) -> Element:
    top_bar = (
        create_top_bar(user_settings, include_sidebar_toggle)
        if include_top_bar
        else None
    )

    return main("#content")[
        top_bar,
        div(class_=outer_classes, id="outer_content_div")[
            div(class_=inner_classes, id="inner_content_div")[content],
        ],
    ]


def create_base_page(
    content: Element,
    user_settings: UserSettings | None,
    page_title: str | None = None,
    include_sidebar: bool = True,
) -> Element:
    toaster = create_toaster_container()
    scripts = [
        script(src="/static/htmx.min.js"),
        script(
            src="https://cdn.jsdelivr.net/npm/@alpinejs/focus@3.14.9/dist/cdn.min.js",
            defer=True,
        ),
        script(
            src="https://cdn.jsdelivr.net/npm/@js-temporal/polyfill@0.5.1/dist/index.umd.min.js",
            defer=False,
        ),
        script(
            src="https://cdn.jsdelivr.net/npm/@alpinejs/persist@3.14.9/dist/cdn.min.js",
            defer=False,
        ),
        script(
            src="https://cdn.jsdelivr.net/npm/@alpinejs/sort@3.x.x/dist/cdn.min.js",
            defer=True,
        ),
        link(
            rel="stylesheet",
            href="https://cdn.jsdelivr.net/npm/basecoat-css@0.3.2/dist/basecoat.cdn.min.css",
        ),
        script(
            src="https://cdn.jsdelivr.net/npm/basecoat-css@0.3.2/dist/js/all.min.js",
            defer=True,
        ),
        # Alpine Core - Must be loaded after plugins
        script(src="/static/alpinejs.3.14.7.min.js", defer=True),
        script(src="/static/d3.v7.min.js"),
        script(src="/static/d3-sankey.min.js"),
        # Add Flatpickr JS
        script(src="https://cdn.jsdelivr.net/npm/flatpickr"),
        script(src="/static/custom_scripts/date_range.js"),
        script(
            src="/static/custom_scripts/app.js", defer=False
        ),  # app.js uses alpine:init, so its defer status is less critical here
        # Duration picker utility
        script(src="/static/custom_scripts/clepsy_chart.js", defer=False),
        script(src="/static/custom_scripts/time_duration_picker.js", defer=False),
    ]

    styles = [
        link(rel="stylesheet", href="https://unpkg.com/easymde/dist/easymde.min.css"),
        link(rel="stylesheet", href="/static/app.css", type="text/css"),
    ]

    header_additions = [
        *styles,
        *scripts,
        link(rel="icon", href="/static/favicon.svg", type="image/svg+xml"),
    ]

    # Create the navbar

    return html(
        x_data="{}",
    )[
        head[
            title[page_title],
            *header_additions,
        ],
        body[create_custom_sidebar() if include_sidebar else None, content, toaster],
    ]
