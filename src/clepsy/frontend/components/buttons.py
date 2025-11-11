from typing import Any, Literal, Optional

from htpy import (
    Element,
    button,
    span,
)

from .icons import IconName, get_icon_svg


ButtonType = Literal[
    "primary",
    "secondary",
    "destructive",
    "outline",
    "ghost",
    "link",
]

ButtonSize = Literal["sm", "lg", "default"]


def create_button(
    text: str | None,
    variant: ButtonType = "primary",
    size: ButtonSize = "default",
    icon: Optional[IconName] = None,
    icon_position: Literal["left", "right"] = "left",
    extra_classes: str = "",
    element_id: Optional[str] = None,
    attrs: Optional[dict[str, Any]] = None,
) -> Element:
    if attrs is None:
        attrs = {}

    # Merge user-provided classes into our computed class list
    user_class = attrs.pop("class", "") or attrs.pop("class_", "")

    size_class_map = {
        "sm": "btn-sm",
        "lg": "btn-lg",
        "default": "",
    }

    variant_class_map = {
        "primary": "btn",
        "secondary": "btn-secondary",
        "destructive": "btn-destructive",
        "outline": "btn-outline",
        "ghost": "btn-ghost",
        "link": "btn-link",
    }

    size_class = size_class_map[size]
    variant_class = variant_class_map[variant]

    # Handle icon-only buttons
    is_icon_only = not text and icon
    if is_icon_only:
        variant_class = f"btn-icon-{variant}" if variant != "primary" else "btn-icon"

    final_classes = f"{variant_class} {size_class} {extra_classes} {user_class}".strip()

    button_content = []

    if icon and icon_position == "left":
        button_content.append(get_icon_svg(icon))
    if text:
        button_content.append(span[text])
    if icon and icon_position == "right":
        button_content.append(get_icon_svg(icon))

    return button(
        class_=final_classes,
        element_id=element_id,
        **attrs,
    )[button_content]
