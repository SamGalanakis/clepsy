from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from clepsy.entities import GoalMetric, MetricOperator


def friendly_metric_name(metric: GoalMetric) -> str:
    match metric:
        case GoalMetric.TOTAL_ACTIVITY_DURATION:
            return "Total Activity Duration"
        case GoalMetric.AVG_PRODUCTIVITY_LEVEL:
            return "Average Productivity Level"
        case _:
            return str(metric)


def friendly_period_name(period: str) -> str:
    match period:
        case "day":
            return "Daily"
        case "week":
            return "Weekly"
        case "month":
            return "Monthly"
        case _:
            return str(period)


def metric_slug(metric: GoalMetric) -> str:
    match metric:
        case GoalMetric.AVG_PRODUCTIVITY_LEVEL:
            return "productivity-average"
        case GoalMetric.TOTAL_ACTIVITY_DURATION:
            return "total-activity-duration"
        case _:
            raise ValueError(f"Unsupported metric: {metric}")


def operator_symbol(op: MetricOperator) -> str:
    match op:
        case MetricOperator.LESS_THAN:
            return "<"
        case MetricOperator.GREATER_THAN:
            return ">"
        case MetricOperator.EQUAL:
            return "="
        case MetricOperator.NOT_EQUAL:
            return "≠"
        case MetricOperator.GREATER_THAN_OR_EQUAL:
            return "≥"
        case MetricOperator.LESS_THAN_OR_EQUAL:
            return "≤"
        case _:
            return "="


def operator_label(op: MetricOperator) -> str:
    match op:
        case MetricOperator.LESS_THAN:
            return "Less than"
        case MetricOperator.GREATER_THAN:
            return "Greater than"
        case MetricOperator.EQUAL:
            return "Equal"
        case MetricOperator.NOT_EQUAL:
            return "Not equal"
        case MetricOperator.GREATER_THAN_OR_EQUAL:
            return "Greater than or equal"
        case MetricOperator.LESS_THAN_OR_EQUAL:
            return "Less than or equal"


def format_productivity_value(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.2f}"


def format_duration_value(value: float | timedelta | None) -> str:
    if value is None:
        return "—"
    seconds: float
    if isinstance(value, timedelta):
        seconds = float(value.total_seconds())
    else:
        try:
            seconds = float(value)
        except (TypeError, ValueError):
            return "—"
    mins_total = int(round(seconds / 60.0))
    hours, minutes = divmod(mins_total, 60)
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def complete_periods_since_created(
    period: str, tz_str: str, created_at_utc: datetime, now_utc: datetime
) -> list[tuple[datetime, datetime]]:
    tz = ZoneInfo(tz_str)
    created_local = created_at_utc.astimezone(tz)
    now_local = now_utc.astimezone(tz)
    out: list[tuple[datetime, datetime]] = []
    if period == "day":
        start_date = created_local.date() + timedelta(days=1)
        last_date = now_local.date() - timedelta(days=1)
        d = start_date
        while d <= last_date:
            s = datetime.combine(d, time.min).replace(tzinfo=tz)
            e = datetime.combine(d, time.max).replace(tzinfo=tz)
            out.append((s.astimezone(timezone.utc), e.astimezone(timezone.utc)))
            d = d + timedelta(days=1)
    elif period == "week":
        days_to_next_monday = (7 - created_local.weekday()) % 7
        if days_to_next_monday == 0:
            days_to_next_monday = 7
        first_monday = created_local.date() + timedelta(days=days_to_next_monday)
        this_monday = now_local.date() - timedelta(days=now_local.weekday())
        last_monday = this_monday - timedelta(weeks=1)
        d = first_monday
        while d <= last_monday:
            s = datetime.combine(d, time.min).replace(tzinfo=tz)
            e = datetime.combine(d + timedelta(days=6), time.max).replace(tzinfo=tz)
            out.append((s.astimezone(timezone.utc), e.astimezone(timezone.utc)))
            d = d + timedelta(weeks=1)
    elif period == "month":
        y, m = created_local.year, created_local.month
        if m == 12:
            y1, m1 = y + 1, 1
        else:
            y1, m1 = y, m + 1
        yn, mn = now_local.year, now_local.month
        if mn == 1:
            y_last, m_last = yn - 1, 12
        else:
            y_last, m_last = yn, mn - 1
        yy, mm = y1, m1
        while (yy < y_last) or (yy == y_last and mm <= m_last):
            s = datetime(yy, mm, 1, 0, 0, 0, tzinfo=tz)
            if mm == 12:
                nm = datetime(yy + 1, 1, 1, 0, 0, 0, tzinfo=tz)
            else:
                nm = datetime(yy, mm + 1, 1, 0, 0, 0, tzinfo=tz)
            e = nm - timedelta(seconds=1)
            out.append((s.astimezone(timezone.utc), e.astimezone(timezone.utc)))
            if mm == 12:
                yy, mm = yy + 1, 1
            else:
                mm = mm + 1
    else:
        return []
    return out
