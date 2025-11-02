from typing import Any, Optional

from htpy import Element, div

from .buttons import ButtonType, create_button
from .icons import IconName


def create_popover(
    base_id: str,
    *,
    trigger_text: str | None = None,
    trigger_variant: ButtonType = "secondary",
    trigger_icon: Optional[IconName] = None,
    trigger_extra_classes: str = "",
    trigger_attrs: Optional[dict[str, Any]] = None,
    content: Element | list[Element] | None = None,
    popover_extra_classes: str = "",
    wrapper_extra_classes: str = "",
) -> Element:
    trigger_attrs = dict(trigger_attrs or {})
    # Allow consumers to extend classes on the trigger via attrs["class"] or class_
    user_trigger_class = trigger_attrs.pop("class", "") or trigger_attrs.pop(
        "class_", ""
    )
    final_trigger_classes = " ".join(
        filter(None, [trigger_extra_classes, user_trigger_class])
    )

    # Ensure required ARIA linkage
    trigger_attrs.update(
        {
            "id": f"{base_id}-trigger",
            "type": "button",
            "aria-expanded": "false",
            "aria-controls": f"{base_id}-popover",
        }
    )

    trigger_btn = create_button(
        text=trigger_text,
        variant=trigger_variant,
        icon=trigger_icon,  # icon-only when text is None
        extra_classes=final_trigger_classes,
        attrs=trigger_attrs,
    )

    # Popover panel (hidden by default, shown by Basecoat JS via [data-popover])
    panel = div(
        id=f"{base_id}-popover",
        **{"data-popover": True, "aria-hidden": "true"},
        class_=(popover_extra_classes or ""),
    )[content]

    return div(id=base_id, class_=("popover " + (wrapper_extra_classes or "")).strip())[
        trigger_btn,
        panel,
    ]
