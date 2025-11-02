from datetime import date, datetime
import json
from typing import Any, Literal, Optional
from zoneinfo import available_timezones

from htpy import Element, div, input as htpy_input, label


common_timezones_list = sorted(list(available_timezones()))
default_python_datetime_format = "%d-%m-%Y %H:%M:%S"


def create_datetimepicker(
    element_id: str,
    name: str,
    title: str,
    initial_value: datetime | date | None = None,
    placeholder: str = "",
    mode: Literal["single", "multiple", "range"] = "single",
    enable_time: bool = True,
    date_format: str = "d-m-Y H:i:S",
    python_datetime_format: str = default_python_datetime_format,
    no_calendar: bool = False,
    time_24hr: bool = True,
    min_date: Optional[date] = None,
    max_date: Optional[date] = None,
    range_separator: Optional[str] = None,
    min_time: Optional[str] = None,
    max_time: Optional[str] = None,
    extra_classes: str | None = None,
    attrs: Optional[dict[str, Any]] = None,
    required: bool = True,
    alt_format: str | None = "d-m-Y H:i",
    use_alt_format: bool = True,
    disabled: bool = False,
    append_to_selector: Optional[str] = None,
    append_to_closest_selector: Optional[str] = None,
) -> Element:
    assert not (
        append_to_closest_selector and append_to_selector
    ), "Use only one of append_to_selector or append_to_closest_selector"
    if mode == "range" and no_calendar:
        raise ValueError(
            "Time-only range mode is not supported. Use create_time_range instead."
        )

    attrs = attrs or {}
    input_classes = "flatpickr input"

    # Option fragments
    extra_cfg = ""
    if range_separator is not None:
        extra_cfg += f'\n    rangeSeparator: "{range_separator}",'
    if min_time is not None:
        extra_cfg += f"\n    minTime: {json.dumps(min_time)},"
    if max_time is not None:
        extra_cfg += f"\n    maxTime: {json.dumps(max_time)},"

    # Append target: explicit > closest > nearest dialog > body
    if append_to_selector:
        append_to_text = f"document.querySelector('{append_to_selector}')"
    elif append_to_closest_selector:
        append_to_text = f"$el.closest('{append_to_closest_selector}')"
    else:
        append_to_text = """(() => (
          $el.closest('dialog,[role="dialog"],.bc-DialogContent,[data-dialog-root],[data-portal]') || document.body
        ))()"""
    extra_cfg += f"\n    appendTo: {append_to_text},"

    # Default date literal
    match initial_value:
        case datetime() as dt:
            assert dt.tzinfo is None, "initial_value datetime must be timezone-naive"
            default_date_js = f"'{dt.strftime(python_datetime_format)}'"
        case date() as d:
            default_date_js = f"'{d.strftime(python_datetime_format)}'"
        case None:
            default_date_js = "null"
        case _:
            raise TypeError("initial_value must be datetime, date, or None")

    label_elemnent = label(for_=element_id, class_="label")[title] if title else None
    min_date_str = (
        min_date.strftime(default_python_datetime_format) if min_date else "null"
    )
    max_date_str = (
        max_date.strftime(default_python_datetime_format) if max_date else "null"
    )

    input_element = htpy_input(
        type="text",
        id=element_id,
        **attrs,
        name=name,
        data_input=True,
        placeholder=placeholder,
        class_=input_classes,
        required=required,
        disabled=disabled,
        x_data=True,
        x_init=f"""(() => {{
  // High z-index so overlays don't bury it
  if (!document.getElementById('fp-zfix')) {{
    const s = document.createElement('style');
    s.id = 'fp-zfix';
    s.textContent = `.flatpickr-calendar{{z-index:2147483647 !important;}}`;
    document.head.appendChild(s);
  }}

  const cfg = {{
    wrap: false,
    mode: "{mode}",
    altFormat: "{alt_format or ""}",
    altInput: {str(use_alt_format).lower()},
    enableTime: {str(enable_time).lower()},
    dateFormat: "{date_format}",
    noCalendar: {str(no_calendar).lower()},
    time_24hr: {str(time_24hr).lower()},
    defaultDate: {default_date_js},
    minDate: {min_date_str},
    maxDate: {max_date_str},
    minuteIncrement: 1,
    allowInput: true,{extra_cfg}
    // Stop built-in placement to avoid the initial jump
    onPreCalendarPosition: () => false,
    onReady: (_, __, inst) => {{
      if (inst.altInput) inst.set("positionElement", inst.altInput); // anchor to visible input
      inst._positionCalendar = () => {{}}; // disable FP reposition entirely
    }},
    onOpen: (_, __, inst) => {{
      const cal = inst.calendarContainer;
      const anchor = inst.altInput || inst._input || $el;

      // Allow overflow from dialog while calendar is open
      const dialogPanel =
        anchor.closest('dialog,[role="dialog"],.bc-DialogContent,[data-dialog-root]') || null;
      const prevOverflow = dialogPanel ? dialogPanel.style.overflow : null;
      if (dialogPanel) dialogPanel.style.overflow = 'visible';

      // One-time placement: directly below the input
      cal.style.position = 'fixed';
      cal.style.pointerEvents = 'auto';

      const r = anchor.getBoundingClientRect();
      let left = r.left;
      let top  = r.bottom + 4; // always below

      // simple clamp so it doesn't go off-screen
      const w = cal.offsetWidth  || 300;
      const h = cal.offsetHeight || 320;
      left = Math.min(Math.max(left, 8), window.innerWidth  - w - 8);
      top  = Math.min(Math.max(top , 8), window.innerHeight - h - 8);

      cal.style.left = left + 'px';
      cal.style.top  = top  + 'px';

      // store cleanup
      inst.__cleanup = () => {{
        if (dialogPanel) dialogPanel.style.overflow = prevOverflow ?? '';
      }};
      cal.addEventListener('click', e => e.stopPropagation(), {{ once: true }});
    }},
    onClose: (_, __, inst) => {{
      if (inst.__cleanup) inst.__cleanup();
    }},
  }};

  $nextTick(() => {{
    const fp = flatpickr($el, cfg);
    if (fp && fp.altInput && {str(required).lower()}) {{
      fp.altInput.required = true;
      $el.required = false;
    }}
  }});
}})()""",
    )

    content = [label_elemnent, input_element]
    container_classes = f"grid gap-3 {extra_classes or ''}".strip()
    return div(class_=container_classes)[content]


def create_time_range(
    start_id: str,
    start_name: str,
    end_id: str,
    end_name: str,
    title: str,
    placeholder_start: str = "Start time",
    placeholder_end: str = "End time",
    time_24hr: bool = True,
    # Backward-compat for global bounds
    min_time: Optional[str] = None,
    max_time: Optional[str] = None,
    # New: per-end bound controls
    start_min_time: Optional[str] = None,
    start_max_time: Optional[str] = None,
    end_min_time: Optional[str] = None,
    end_max_time: Optional[str] = None,
    # Defaults
    default_start: Optional[str] = None,
    default_end: Optional[str] = None,
    required: bool = True,
    base_classes_override: str | None = None,
    extra_classes: str | None = None,
    attrs: Optional[dict[str, Any]] = None,
) -> Element:
    """
    Independent time range picker (Flatpickr time-only) with validation.

    - End is disabled until start has a value.
    - End minTime is kept >= start.
    - Prevents form submission if end <= start and shows an error.
    - Supports default values and per-end min/max bounds.
    """
    attrs = attrs or {}

    # Resolve final min/max for each side, falling back to global min_time/max_time
    start_min_js = (
        json.dumps(start_min_time or min_time)
        if (start_min_time or min_time)
        else "null"
    )
    start_max_js = (
        json.dumps(start_max_time or max_time)
        if (start_max_time or max_time)
        else "null"
    )
    end_min_js = (
        json.dumps(end_min_time or min_time) if (end_min_time or min_time) else "null"
    )
    end_max_js = (
        json.dumps(end_max_time or max_time) if (end_max_time or max_time) else "null"
    )
    default_start_js = json.dumps(default_start) if default_start else "null"
    default_end_js = json.dumps(default_end) if default_end else "null"

    wrapper_classes = (
        base_classes_override
        if base_classes_override is not None
        else "relative flex w-full max-w-xs flex-col gap-1 text-on-surface"
    )
    final_classes = f"{wrapper_classes} {extra_classes or ''}".strip()

    # Shared input classes (keep consistent with other inputs)
    input_classes = "rounded-radius input"

    # Alpine controller builds both flatpickr instances and validates
    x_data = f"""
{{
    fpStart: null,
    fpEnd: null,
    init() {{
        const startInput = this.$refs.startInput;
        const endInput = this.$refs.endInput;
        const parse = (s) => {{
            if (!s) return null;
            const parts = s.split(':').map(n=>parseInt(n,10));
            const h = parts[0]||0, m = parts[1]||0, sec = parts[2]||0;
            return h*3600 + m*60 + sec;
        }};
        const setError = (show) => {{
            const el = this.$refs.error;
            if (!el) return;
            if (show) el.classList.remove('hidden'); else el.classList.add('hidden');
        }};
        const validate = () => {{
            const a = parse(startInput.value);
            const b = parse(endInput.value);
            const ok = (a !== null && b !== null && b > a);
            setError(!ok);
            return ok;
        }};

        const startOpts = {{
            enableTime: true, noCalendar: true, dateFormat: 'H:i', altFormat: 'H:i', altInput: true, time_24hr: {str(time_24hr).lower()}, disableMobile: true,
            minTime: {start_min_js}, maxTime: {start_max_js},
            defaultDate: {default_start_js},
            onChange: (dates, str) => {{
                if (!str) {{
                    endInput.disabled = true;
                    if (this.fpEnd) this.fpEnd.set('minTime', {end_min_js});
                }} else {{
                    endInput.disabled = false;
                    if (this.fpEnd) this.fpEnd.set('minTime', str);
                }}
                validate();
            }}
        }};

        const endOpts = {{
            enableTime: true, noCalendar: true, dateFormat: 'H:i', altFormat: 'H:i', altInput: true, time_24hr: {str(time_24hr).lower()}, disableMobile: true,
            minTime: {end_min_js}, maxTime: {end_max_js},
            defaultDate: {default_end_js},
            onChange: () => validate()
        }};

        this.fpStart = flatpickr(startInput, startOpts);
        this.fpEnd = flatpickr(endInput, endOpts);

        // Initial end disabled state and constraint
        if (!startInput.value) {{ endInput.disabled = true; }}
        else {{ this.fpEnd.set('minTime', startInput.value); }}

        // Submission validation hook
        ;[startInput, endInput].forEach(input => {{
            if (input.form) {{
                input.form.addEventListener('submit', (e) => {{ if (!validate()) e.preventDefault(); }});
            }}
        }});
    }}
}}
"""

    return div(class_=final_classes, x_data=x_data, **attrs)[
        label(
            class_="w-fit pl-0.5 text-sm font-medium text-on-surface dark:text-on-surface-dark mb-1"
        )[title],
        div(class_="flex items-center gap-2")[
            htpy_input(
                type="text",
                id=start_id,
                name=start_name,
                placeholder=placeholder_start,
                class_=input_classes,
                required=required,
                **{"x-ref": "startInput"},
            ),
            htpy_input(
                type="text",
                id=end_id,
                name=end_name,
                placeholder=placeholder_end,
                class_=input_classes,
                required=required,
                **{"x-ref": "endInput"},
            ),
        ],
        div(**{"x-ref": "error"}, class_="text-sm text-error hidden mt-1")[
            "End time must be after start time."
        ],
    ]
