from datetime import datetime, timedelta

from htpy import Element, div

from clepsy.frontend.components import create_button


def create_chevron_forward_backward_buttons() -> Element:
    """Render left/right chevrons that adjust the Alpine 'offset' model."""
    left_chevron_button = create_button(
        text="",
        icon="chevron-left",
        variant="secondary",
        attrs={"@click": "offset-=1;"},
    )

    right_chevron_button = create_button(
        text="",
        icon="chevron-right",
        variant="secondary",
        attrs={"@click": "offset+=1;"},
    )

    return div(class_="flex items-center justify-between")[
        div(class_="flex items-center")[left_chevron_button, right_chevron_button]
    ]


def format_compact_weekly_range(
    start_time_user_tz: datetime, end_time_user_tz: datetime
) -> str:
    """Return a compact weekly date range string (end is exclusive).

    Same month → "12–18 Aug"
    Different months (same year) → "28 Aug – 3 Sep"
    Different years → include years → "30 Dec 2024 – 5 Jan 2025"
    """
    start_date = start_time_user_tz.date()
    end_date_inclusive = (end_time_user_tz - timedelta(days=1)).date()

    same_year = start_date.year == end_date_inclusive.year
    same_month = start_date.month == end_date_inclusive.month and same_year

    if not same_year:
        return (
            f"{start_date.day} {start_time_user_tz.strftime('%b')} {start_date.year} – "
            f"{end_date_inclusive.day} {end_time_user_tz.strftime('%b')} {end_date_inclusive.year}"
        )
    if not same_month:
        return (
            f"{start_date.day} {start_time_user_tz.strftime('%b')} – "
            f"{end_date_inclusive.day} {end_time_user_tz.strftime('%b')}"
        )
    return (
        f"{start_date.day}–{end_date_inclusive.day} {start_time_user_tz.strftime('%b')}"
    )


def create_current_time_range_visualiser() -> Element:
    """Label that shows the current date range; final text is bound via JS (x-text)."""

    return div(
        class_=(
            "flex items-center px-3 py-1.5 text-sm font-medium text-foreground "
            "bg-muted/50 rounded-md border"
        ),
        **{
            "x-text": "window.formatDateRangeLabel(reference_date, view_mode, offset)",
        },
    )


def create_time_nav_group() -> Element:
    """Current range label + left/right chevrons."""
    time_range_visualizer = create_current_time_range_visualiser()
    chevron_buttons = create_chevron_forward_backward_buttons()
    return div(class_="flex items-center gap-3")[time_range_visualizer, chevron_buttons]
