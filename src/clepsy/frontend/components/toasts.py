from typing import Literal, Optional, TypedDict

from htpy import (
    Element,
    button,
    circle,
    div,
    footer,
    h2,
    img,
    p,
    path,
    section,
    svg,
)


class Sender(TypedDict, total=False):
    name: str
    avatar: str


def _get_icon(category: Literal["success", "info", "warning", "error"]) -> Element:
    icon_paths = {
        "success": [
            circle(cx="12", cy="12", r="10"),
            path(d="m9 12 2 2 4-4"),
        ],
        "info": [
            circle(cx="12", cy="12", r="10"),
            path(d="M12 16v-4"),
            path(d="M12 8h.01"),
        ],
        "warning": [
            circle(cx="12", cy="12", r="10"),
            path(d="M12 8v4"),
            path(d="M12 16h.01"),
        ],
        "error": [
            circle(cx="12", cy="12", r="10"),
            path(d="m15 9-6 6"),
            path(d="m9 9 6 6"),
        ],
    }
    return svg(
        aria_hidden="true",
        xmlns="http://www.w3.org/2000/svg",
        width="24",
        height="24",
        viewBox="0 0 24 24",
        fill="none",
        stroke="currentColor",
        stroke_width="2",
        stroke_linecap="round",
        stroke_linejoin="round",
    )[icon_paths[category]]


def create_toast(
    category: Literal["success", "info", "warning", "error"],
    title: str,
    description: Optional[str] = None,
    duration: int = 5000,
    cancel_label: str = "Dismiss",
    attrs: dict | None = None,
) -> Element:
    """Creates a standard toast component."""
    attrs = attrs or {}
    user_class = attrs.pop("class", "") or attrs.pop("class_", "") if attrs else ""
    toast_attrs = {
        "class": f"toast {user_class}".strip(),
        "role": "status",
        "aria-atomic": "true",
        "aria-hidden": "false",
        "data-category": category,
        "data-duration": str(duration),
    }

    toast_content = [
        _get_icon(category),
        section()[h2()[title]],
        footer()[
            button(type="button", class_="btn", data_toast_action=True)[cancel_label]
        ],
    ]

    if description:
        toast_content[1][p()[description]]

    return div(**{**toast_attrs, **attrs})[div(class_="toast-content")[toast_content]]


def create_message_toast(
    sender: Sender,
    message: str,
    duration: int = 8000,
    attrs: dict | None = None,
) -> Element:
    """Creates a message toast component."""
    attrs = attrs or {}
    user_class = attrs.pop("class", "") or attrs.pop("class_", "") if attrs else ""
    toast_attrs = {
        "class": f"toast {user_class}".strip(),
        "role": "status",
        "aria-atomic": "true",
        "aria-hidden": "false",
        "data-duration": str(duration),
    }

    toast_content = [
        img(
            class_="mr-2 size-12 rounded-full",
            alt="avatar",
            aria_hidden="true",
            src=sender.get("avatar", ""),
        ),
        section()[
            h2()[sender.get("name", "Anonymous")],
            p()[message],
        ],
        footer()[
            button(type="button", class_="btn")["Reply"],
            button(type="button", class_="btn-outline", data_toast_action=True)[
                "Dismiss"
            ],
        ],
    ]

    return div(**{**toast_attrs, **attrs})[div(class_="toast-content")[toast_content]]


def create_toaster_container() -> Element:
    """
    Creates the main container for toasts.
    This should be placed once in your base layout.
    """
    return div(id="toaster", class_="toaster", data_align="end")
