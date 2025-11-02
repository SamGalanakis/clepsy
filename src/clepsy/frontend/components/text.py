from typing import Any, Optional

from htpy import Element, div, input as htpy_input, label, p, script, textarea


def create_text_input(
    element_id: str | None = None,
    name: str | None = None,
    title: str | None = None,
    placeholder: str | None = "",
    value: str = "",
    required: bool = False,
    readonly: bool = False,
    disabled: bool = False,
    extra_classes: str | None = None,
    description: str | None = None,
    valid_state: bool = True,
    attrs: Optional[dict[str, Any]] = None,
) -> Element:
    """
    Creates a styled text input component based on Basecoat UI.
    """

    placeholder = placeholder or ""

    input_attrs = {
        "id": element_id,
        "name": name,
        "class": "input",
        "placeholder": placeholder,
        "value": value,
    }
    if required:
        input_attrs["required"] = True
    if readonly:
        input_attrs["readonly"] = True
    if disabled:
        input_attrs["disabled"] = True

    if not valid_state:
        input_attrs["aria-invalid"] = "true"

    container_classes = f"grid gap-3 {extra_classes or ''}".strip()

    merged_input_attrs: dict[str, Any] = {
        **input_attrs,
        **(attrs or {}),
    }

    content = [
        label(for_=element_id, class_="label")[title] if title else None,
        htpy_input(**merged_input_attrs),
    ]

    if description:
        content.append(p(class_="text-muted-foreground text-sm")[description])

    return div(class_=container_classes)[content]


def create_text_area(
    element_id: str | None,
    name: str,
    title: str,
    placeholder: str = "",
    value: str = "",
    required: bool = False,
    readonly: bool = False,
    disabled: bool = False,
    rows: int = 3,
    extra_classes: str | None = None,
    description: str | None = None,
    attrs: Optional[dict[str, Any]] = None,
) -> Element:
    """
    Creates a styled textarea component based on Basecoat UI.
    """
    textarea_attrs = {
        "id": element_id,
        "name": name,
        "class": "textarea",
        "placeholder": placeholder,
        "rows": rows,
    }
    if required:
        textarea_attrs["required"] = True
    if readonly:
        textarea_attrs["readonly"] = True
    if disabled:
        textarea_attrs["disabled"] = True

    container_classes = f"grid gap-3 {extra_classes or ''}".strip()

    # Merge attributes with precedence: component defaults < attrs (preferred)
    merged_textarea_attrs: dict[str, Any] = {**textarea_attrs, **(attrs or {})}

    content = [
        label(for_=element_id, class_="label")[title],
        textarea(**merged_textarea_attrs)[value],
    ]

    if description:
        content.append(p(class_="text-muted-foreground text-sm")[description])

    return div(class_=container_classes)[content]


def create_markdown_editor(
    element_id: str | None,
    name: str,
    title: str,
    placeholder: str = "",
    value: str = "",
    required: bool = False,
    readonly: bool = False,
    disabled: bool = False,
    x_model: str | None = None,
    height: str = "300px",
    toolbar_config: list | None = None,
    base_classes_override: str | None = None,
    extra_classes: str | None = None,
    attrs: Optional[dict[str, Any]] = None,
) -> Element:
    default_toolbar = [
        "bold",
        "italic",
        "heading",
        "|",
        "quote",
        "unordered-list",
        "ordered-list",
        "|",
        #     "link",
        #     "image",
        #     "|",
        "preview",
        #      "side-by-side",
        #     "fullscreen",
        #      "|",
        #      "guide",
    ]
    toolbar = toolbar_config or default_toolbar

    init_script = f"""
  this.editor = new EasyMDE({{
    element: $refs.textarea,
    placeholder: `{placeholder}`,
    toolbar: {toolbar},
    forceSync: true,
    status: false,
    spellChecker: false,
    hideIcons: ['guide'],
    showIcons: ['code', 'table'],
    minHeight: '{height}',

    renderingConfig: {{ codeSyntaxHighlighting: true }},
    {"readOnly: 'nocursor'," if disabled else ("readOnly: true," if readonly else "")}
  }});
"""

    outer_div = (
        base_classes_override
        or "flex w-full flex-col gap-1 text-on-surface dark:text-on-surface-dark"
    )
    return div(
        class_=f"{outer_div} {extra_classes or ''}".strip(),
        x_data=True,
        x_init=init_script,
        **(attrs or {}),
    )[
        label(for_=element_id, class_="w-fit pl-0.5 text-sm")[title],
        script(src="https://unpkg.com/easymde/dist/easymde.min.js"),
        div(class_="markdown-editor-wrapper")[
            textarea(
                id=element_id,
                name=name,
                x_model=x_model,
                required=required,
                readonly=readonly,
                disabled=disabled,
                value=value,
                x_ref="textarea",
                class_="prose hidden",
            )[value],
        ],
    ]
