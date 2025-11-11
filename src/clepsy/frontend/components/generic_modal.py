from typing import Any, List, Optional

from htpy import Element, dialog, div


def create_generic_modal(
    modal_id: str,
    content_id: str,
    children: Optional[List[Element] | Element] = None,
    extra_classes: str = "",
    attrs: Optional[dict[str, Any]] = None,
) -> Element:
    """
    Creates a generic modal using the <dialog> element, styled with basecoat-like classes.
    The modal is controlled via JavaScript by calling .showModal() and .close().

    :param modal_id: The ID for the <dialog> element.
    :param content_id: The ID for the main content div inside the modal.
    :param children: Optional initial content for the modal.
    :param extra_classes: Extra CSS classes for the <dialog> element.
    :param attrs: Extra HTML attributes for the <dialog> element.
    :return: An htpy Element representing the modal.
    """
    attrs = attrs or {}
    user_class = attrs.pop("class", "") or attrs.pop("class_", "") if attrs else ""

    content_div = div(id=content_id, class_="dialog__content")[children]

    modal = dialog(
        id=modal_id,
        class_=f"dialog {extra_classes} {user_class}".strip(),
        **{
            "x-data": "{}",
            "@closemodal.window": """
    if (!$event.detail.id || $event.detail.id === $el.id) {
      $el.close()
    }""",
        },
        **attrs,
    )[Element("article")[content_div]]

    return modal
