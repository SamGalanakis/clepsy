from typing import Any, Literal, Optional

from htpy import Element, button, div, span
from loguru import logger


TooltipPosition = Literal["top", "bottom", "left", "right"]
TooltipAlign = Literal["start", "center", "end"]


def create_tooltip(
    button_text: str,
    tooltip_text: str,
    side: TooltipPosition = "top",
    align: TooltipAlign = "center",
    extra_classes: str | None = None,
    attrs: Optional[dict[str, Any]] = None,
) -> Element:
    # Self-contained tooltip using group-hover pattern (no data-tooltip).
    if attrs is None:
        attrs = {}

    if "class" in attrs:
        logger.warning(
            "Passing 'class' in attrs overrides default classes; "
            "use 'extra_classes' to append instead."
        )

    # Default trigger type
    attrs["type"] = attrs.get("type", "button")

    # Compose trigger classes
    class_val = ("btn-outline " + (extra_classes or "")).strip()

    # Build class-based positioning and animation (group-hover)
    bubble_classes = [
        "absolute",
        "invisible",
        "opacity-0",
        "group-hover:visible",
        "group-hover:opacity-100",
        "group-focus-within:visible",
        "group-focus-within:opacity-100",
        "transition-all",
        "duration-200",
        "ease-out",
        "transform",
        "rounded-md",
        "px-3",
        "py-1.5",
        "text-xs",
        "text-left",
        # width behavior: single line until 20rem, then wrap
        "inline-block",
        "w-max",
        "max-w-xs",
        "box-border",
        "whitespace-normal",
        "break-normal",
        "pointer-events-none",
        "z-[60]",
    ]

    # Side offsets and appear animations
    if side == "top":
        bubble_classes += [
            "bottom-full",
            "mb-1.5",
            "translate-y-2",
            "group-hover:translate-y-0",
        ]
    elif side == "bottom":
        bubble_classes += [
            "top-full",
            "mt-1.5",
            "-translate-y-2",
            "group-hover:translate-y-0",
        ]
    elif side == "left":
        bubble_classes += [
            "right-full",
            "mr-1.5",
            "translate-x-2",
            "group-hover:translate-x-0",
        ]
    else:  # right
        bubble_classes += [
            "left-full",
            "ml-1.5",
            "-translate-x-2",
            "group-hover:translate-x-0",
        ]

    # Alignment
    if side in ("top", "bottom"):
        if align == "start":
            bubble_classes += ["left-0"]
        elif align == "end":
            bubble_classes += ["right-0"]
        else:
            bubble_classes += ["left-1/2", "-translate-x-1/2"]
    else:  # left/right
        if align == "start":
            bubble_classes += ["top-0"]
        elif align == "end":
            bubble_classes += ["bottom-0"]
        else:
            bubble_classes += ["top-1/2", "-translate-y-1/2"]

    # Only theme colors inline; everything else via classes
    bubble_style = (
        "background: var(--color-primary, hsl(var(--primary))); "
        "color: var(--color-primary-foreground, hsl(var(--primary-foreground))); "
        "box-sizing: border-box;"
    )

    # Wrapper provides positioning and hover group (delegated events via script)
    return div(
        class_="relative inline-flex align-middle !overflow-visible group",
        **{
            "data-clp-tooltip": "",
        },
    )[
        button(class_=class_val, **attrs)[button_text],
        span(
            role="tooltip",
            class_=" ".join(bubble_classes),
            style=bubble_style,
        )[tooltip_text],
    ]
