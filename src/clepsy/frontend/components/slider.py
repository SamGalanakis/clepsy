from typing import Any, Optional

from htpy import Element, div, input as htpy_input, label, span


def create_slider(
    element_id: str,
    name: str | None,
    title: str | None = None,
    min_value: float = 0,
    max_value: float = 100,
    step: float = 1,
    value: float | None = None,
    show_value: bool = False,
    value_suffix: str | None = None,
    base_classes_override: str | None = None,
    extra_classes: str | None = None,
    attrs: Optional[dict[str, Any]] = None,
) -> Element:
    """
    Creates a styled range slider component in the same style as other inputs.

    - Uses class "input w-full" to match Basecoat form styles.
    - Maintains a CSS variable `--slider-value` (0–100%) for track styling.
    - Optionally shows a live-updating value label.
    """

    outer_div = (
        base_classes_override
        if base_classes_override is not None
        else "flex w-full flex-col gap-1 text-on-surface dark:text-on-surface-dark"
    )

    # Inline gradient uses currentColor so applying a text-* utility or theme color
    # to the input will color the filled track. Default relies on form theme color.
    inline_style = (
        "background: linear-gradient(to right, currentColor 0 var(--slider-value), "
        "color-mix(in oklab, currentColor 20%, transparent) var(--slider-value) 100%);"
    )

    # Initial value fallback
    initial_value = (
        value if value is not None else (min_value + (max_value - min_value) / 2)
    )

    # Alpine controller that updates --slider-value and optional live value
    x_init = """
    const el = $refs.slider;
    const update = () => {
      const min = parseFloat(el.min || 0);
      const max = parseFloat(el.max || 100);
      const val = parseFloat(el.value || min);
      const pct = (max === min) ? 0 : ((val - min) / (max - min)) * 100;
      el.style.setProperty('--slider-value', pct + '%');
      if ($refs.valueEl) {
        $refs.valueEl.textContent = el.value + ($refs.valueEl.dataset.suffix || '');
      }
    };
    update();
    el.addEventListener('input', update);
    """

    label_el = label(for_=element_id, class_="label")[title] if title else None

    value_badge = (
        span(
            **{"x-ref": "valueEl", "data-suffix": value_suffix or ""},
            class_="text-xs text-muted-foreground ml-auto",
        )
        if show_value
        else None
    )

    return div(
        class_=f"{outer_div} {extra_classes or ''}".strip(),
        x_data=True,
        x_init=x_init,
        **(attrs or {}),
    )[
        div(class_="flex items-center gap-2")[
            label_el,
            value_badge,
        ],
        htpy_input(
            type="range",
            id=element_id,
            name=name,
            min=str(min_value),
            max=str(max_value),
            step=str(step),
            value=str(initial_value),
            class_="input w-full",
            style=inline_style,
            **{"x-ref": "slider"},
        ),
    ]
