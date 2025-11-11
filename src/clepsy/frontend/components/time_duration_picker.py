from datetime import timedelta
from typing import Any, Optional

from htpy import Element, button, div, input as htpy_input, label, span


def create_time_duration_picker(
    *,
    element_id: str,
    name: str,
    title: str | None = None,
    include_seconds: bool = False,
    min_duration: timedelta | None = None,
    max_duration: timedelta | None = None,
    initial_duration: timedelta = timedelta(0),
    base_classes: str = "html-duration-picker-input-controls-wrapper justify-self-start",
    extra_classes: str = "w-[10ch] sm:w-[12ch]",  # "w-[10ch] sm:w-[12ch]",
    attrs: Optional[dict[str, Any]] = None,
) -> Element:
    """Render a duration picker with a formatted display input and a hidden seconds field.

    - include_seconds: whether to use HH:MM:SS (True) or HH:MM (False)
    - min_duration / max_duration: constraints as timedelta; defaults to 0 .. 99:59:59
    - initial_duration: initial value as timedelta (defaults to 0)
    - name: the hidden input's name that is submitted with the form
    - base_classes: base classes applied to the wrapper (defaults to compact inline)
    - extra_classes: appended classes for the wrapper (empty by default)
    """

    attrs = attrs or {}
    disp_id = f"{element_id}-display"
    hidden_id = element_id

    # Helpers to convert to seconds
    def _to_seconds(td: timedelta | None, default: int) -> int:
        if td is None:
            return default
        try:
            return int(td.total_seconds())
        except Exception:
            return default

    def _fmt2(num: int) -> str:
        # Hours zero-padded to at least 2 (keeps 3+ digits intact)
        return f"0{num}" if num < 10 else str(num)

    def _format_hhmmss(total_seconds: int, include_secs: bool) -> str:
        if total_seconds < 0:
            total_seconds = 0
        h = total_seconds // 3600
        rem = total_seconds % 3600
        m = rem // 60
        s = rem % 60
        if include_secs:
            return f"{_fmt2(h)}:{m:02d}:{s:02d}"
        return f"{_fmt2(h)}:{m:02d}"

    # Defaults
    min_seconds = _to_seconds(min_duration, 0)
    # 99:59:59 -> 359,999 seconds
    max_seconds = _to_seconds(max_duration, 99 * 3600 + 59 * 60 + 59)
    initial_seconds = _to_seconds(initial_duration, 0)

    # Placeholder always derived from initial
    placeholder = (
        _format_hhmmss(initial_seconds, include_seconds)
        if initial_seconds
        else ("00:00:00" if include_seconds else "00:00")
    )

    label_el = label(class_="label")[title] if title else None

    input_el = htpy_input(
        type="text",
        id=disp_id,
        placeholder=placeholder,
        class_=("input html-duration-picker w-full"),
        **{
            "data-duration-picker": "true",
            "data-include-seconds": str(include_seconds).lower(),
            "data-min": str(min_seconds),
            "data-max": str(max_seconds),
            "data-target-id": hidden_id,
            "data-initial": str(initial_seconds or 0),
            "inputmode": "numeric",
            # Simple pattern hints; exact validation happens in JS
            "pattern": r"^[0-9]{1,9}:[0-5][0-9](:[0-5][0-9])?$"
            if include_seconds
            else r"^[0-9]{1,9}:[0-5][0-9]$",
        },
        **attrs,
    )

    hidden_el = htpy_input(
        type="hidden",
        id=hidden_id,
        name=name,
        value=str(initial_seconds or 0),
    )

    controls = div(
        class_="controls",
        **{"data-dp-controls": ""},
    )[
        button(
            type="button",
            class_="scroll-btn",
            **{"data-dp-action": "inc", "aria-label": "Increment"},
        )[span(class_="caret caret-up")],
        button(
            type="button",
            class_="scroll-btn",
            **{"data-dp-action": "dec", "aria-label": "Decrement"},
        )[span(class_="caret caret-down")],
    ]

    # Build wrapper classes from base and extras
    wrapper_classes = base_classes
    if extra_classes:
        wrapper_classes = f"{wrapper_classes} {extra_classes}"

    wrapper = div(
        class_=wrapper_classes,
        **{"data-duration-picker-wrapper": ""},
    )[input_el, controls]

    container_classes = "grid gap-2"
    return div(class_=container_classes)[label_el, wrapper, hidden_el]
