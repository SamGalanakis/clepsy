import base64
from datetime import date as datetime_date, datetime, timedelta, timezone
import io
import math
import os
import re
from typing import Callable, Sequence, TypeVar
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from baml_py import FunctionLog, Image as BamlImage
from dateutil.relativedelta import relativedelta
from loguru import logger
from PIL import Image
from unidecode import unidecode

import baml_client.types as baml_types
from clepsy.config import config
from clepsy.entities import (
    ActivityEvent,
    ActivityEventType,
    CheckWithError,
    TimeSpan,
    ViewMode,
)
from clepsy.human_readable_pw import generate_typable_password


def count_words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def truncate_words(text: str, max_words: int) -> str:
    assert max_words > 0, "max_words must be positive"

    assert text, "text must be non-empty"

    truncated_end: int | None = None
    for idx, match in enumerate(re.finditer(r"\S+", text), start=1):
        if idx == max_words:
            truncated_end = match.end()
            break

    if truncated_end is None:
        return text

    return text[:truncated_end]


def overlap_in_span(
    a: list[tuple[float, bool]], b: list[tuple[float, bool]], span: tuple[float, float]
) -> bool:
    start, end = span
    if not (start < end):
        raise ValueError("span_of_interest must be (start, end) with start < end")

    i = j = 0
    on_a = on_b = True  # traces always start ON

    # fast‑forward each list to the first event ≥ span_start
    while i < len(a) and a[i][0] < start:
        on_a = a[i][1]
        i += 1
    while j < len(b) and b[j][0] < start:
        on_b = b[j][1]
        j += 1

    if on_a and on_b:  # already overlapping at span_start
        return True

    # merge‑scan until span_end
    while True:
        next_a = a[i][0] if i < len(a) and a[i][0] < end else end
        next_b = b[j][0] if j < len(b) and b[j][0] < end else end
        nxt = min(next_a, next_b)

        if nxt >= end:  # reached span_end → done
            return False

        if next_a == nxt:  # process A’s event
            on_a = a[i][1]
            i += 1
        else:  # process B’s event
            on_b = b[j][1]
            j += 1

        if on_a and on_b:  # overlap begins at `nxt`
            return True


MINUTES_SECONDS_REGEX = re.compile(r"^([0-5]?[0-9])m([0-5]?[0-9])s$")


def format_function_log(function_log: FunctionLog) -> str:
    duration = (
        function_log.timing.duration_ms / 1000
        if function_log.timing.duration_ms
        else "N/A"
    )

    body_text = "N/A"
    if function_log.calls:
        last_call = function_log.calls[-1]
        if last_call.http_request:
            body_text = last_call.http_request.body.text()

    return (
        f"Http call body:{body_text}\n"
        f"Function: {function_log.function_name} ID: {function_log.id}, "
        f"Timestamp: {function_log.timing.start_time_utc_ms}, "
        f"Duration: {duration}s, "
        f"Raw response: {function_log.raw_llm_response}"
    )


def parse_mm_ss_string(mm_ss: str) -> tuple[int, int]:
    match = MINUTES_SECONDS_REGEX.match(mm_ss)
    if not match:
        raise ValueError(f"Invalid format: {mm_ss}. Expected format is 'MMmSSs'.")

    minutes = int(match.group(1))
    seconds = int(match.group(2))

    return minutes, seconds


def mm_ss_to_timedelta(mm_ss: str) -> timedelta:
    minutes, seconds = parse_mm_ss_string(mm_ss)
    return timedelta(minutes=minutes, seconds=seconds)


def timedelta_to_minutes_seconds(td: timedelta) -> tuple[int, int]:
    total_seconds = int(td.total_seconds())
    minutes, seconds = divmod(total_seconds, 60)
    return minutes, seconds


def calculate_duration(
    events: Sequence[ActivityEvent],
    window_start: datetime | None,
    window_end: datetime,
) -> timedelta:
    if window_start and window_end < window_start:
        raise ValueError("window_end must be greater than or equal to window_start")

    sorted_events = sorted(events, key=lambda e: e.event_time)
    total_duration = timedelta(0)
    current_open_time: datetime | None = None

    for event in sorted_events:
        event_time = event.event_time
        if event.event_type == ActivityEventType.OPEN:
            # keep the earliest open within the active stretch
            if current_open_time is None:
                current_open_time = event_time
        else:  # CLOSE
            if current_open_time is None:
                continue

            interval_start = current_open_time
            interval_end = event_time

            if window_start and interval_end <= window_start:
                current_open_time = None
                continue

            if window_start and interval_start < window_start:
                interval_start = window_start

            if interval_end > window_end:
                interval_end = window_end

            if interval_end > interval_start:
                total_duration += interval_end - interval_start

            current_open_time = None

            if interval_end >= window_end:
                break

    if current_open_time is not None:
        interval_start = current_open_time
        if window_start and interval_start < window_start:
            interval_start = window_start
        interval_end = window_end
        if interval_end > interval_start:
            total_duration += interval_end - interval_start

    return total_duration


def calculate_activity_gaps(
    events_by_activity: Sequence[Sequence[ActivityEvent]],
    *,
    window_start: datetime | None = None,
    window_end: datetime,
) -> tuple[timedelta, float]:
    if window_end is None:
        raise ValueError("window_end must be provided")

    if window_start and window_end < window_start:
        raise ValueError("window_end must be greater than or equal to window_start")

    initial_active = 0

    timeline: list[tuple[datetime, int]] = []
    earliest_event_time: datetime | None = None
    for event_list in events_by_activity:
        if not event_list:
            continue

        if window_start is None:
            first_time = event_list[0].event_time
            if earliest_event_time is None or first_time < earliest_event_time:
                earliest_event_time = first_time

        idx = 0
        active = False

        if window_start is not None:
            while idx < len(event_list) and event_list[idx].event_time < window_start:
                active = event_list[idx].event_type == ActivityEventType.OPEN
                idx += 1

        if active:
            initial_active += 1

        while idx < len(event_list):
            event = event_list[idx]
            event_time = event.event_time
            if event_time > window_end:
                break
            if window_start is not None and event_time < window_start:
                idx += 1
                continue

            delta = 1 if event.event_type == ActivityEventType.OPEN else -1
            timeline.append((event_time, delta))

            if earliest_event_time is None or event_time < earliest_event_time:
                earliest_event_time = event_time
            idx += 1

    if window_start is not None:
        span_start = window_start
    elif earliest_event_time is not None:
        span_start = earliest_event_time
    elif window_end is not None:
        span_start = window_end
    else:
        return timedelta(0), 0.0

    span_end = window_end

    if span_end <= span_start:
        return timedelta(0), 0.0

    timeline.sort(key=lambda item: item[0])
    merged_timeline: list[tuple[datetime, int]] = []
    for event_time, delta in timeline:
        if event_time < span_start or event_time > span_end:
            continue
        if merged_timeline and merged_timeline[-1][0] == event_time:
            prev_time, prev_delta = merged_timeline[-1]
            merged_timeline[-1] = (prev_time, prev_delta + delta)
        else:
            merged_timeline.append((event_time, delta))

    current_active = initial_active
    max_gap = timedelta(0)
    total_gap = timedelta(0)
    previous_time = span_start

    for event_time, delta in merged_timeline:
        if event_time < previous_time:
            current_active += delta
            continue

        interval = event_time - previous_time
        if interval > timedelta(0) and current_active == 0:
            total_gap += interval
            if interval > max_gap:
                max_gap = interval

        current_active += delta
        previous_time = event_time

    final_interval = span_end - previous_time
    if final_interval > timedelta(0) and current_active == 0:
        total_gap += final_interval
        if final_interval > max_gap:
            max_gap = final_interval

    span_duration = span_end - span_start
    gap_percentage = (
        total_gap.total_seconds() / span_duration.total_seconds()
        if span_duration > timedelta(0)
        else 0.0
    )

    return max_gap, gap_percentage


def mm_ss_to_datetime(start: datetime, minutes: int, seconds: int) -> datetime:
    return start + timedelta(seconds=seconds, minutes=minutes)


def extract_islands(
    intervals: list[TimeSpan], max_gap: timedelta, assume_sorted: bool
) -> list[int]:
    if not assume_sorted:
        intervals = sorted(intervals, key=lambda x: x.start_time)

    island_split_indexes = []

    if not intervals:
        return []

    current_end = intervals[0].end_time
    for index, interval in enumerate(intervals[1:]):
        if interval.start_time - current_end <= max_gap:
            current_end = max(current_end, interval.end_time)
        else:
            island_split_indexes.append(index + 1)
            current_end = interval.end_time

    return island_split_indexes


T = TypeVar("T")


def split_by_indices(seq: Sequence[T], indices: Sequence[int]) -> list[list[T]]:
    result: list[list[T]] = []
    last = 0
    for idx in indices:
        result.append(list(seq[last:idx]))
        last = idx
    result.append(list(seq[last:]))
    return result


def human_delta(delta: timedelta) -> str:
    total_seconds = int(delta.total_seconds())
    if total_seconds < 0:
        total_seconds = abs(total_seconds)

    days, rem = divmod(total_seconds, 86_400)
    hours, rem = divmod(rem, 3_600)
    minutes, seconds = divmod(rem, 60)

    if days:
        return f"{days} day(s) {hours} hr(s) {minutes} min {seconds} sec"
    if hours:
        return f"{hours} hr(s) {minutes} min {seconds} sec"
    if minutes:
        return f"{minutes} min {seconds} sec"
    return f"{seconds} sec"


def mm_ss_string_to_datetime(start: datetime, mm_ss: str) -> datetime:
    minutes, seconds = parse_mm_ss_string(mm_ss)
    return mm_ss_to_datetime(start, minutes, seconds)


def datetime_to_mm_ss(start: datetime, date: datetime) -> baml_types.RelativeTimestamp:
    dt = date - start
    minutes, seconds = timedelta_to_minutes_seconds(dt)
    return baml_types.RelativeTimestamp(
        minutes=minutes,
        seconds=seconds,
    )


def overlapping_subarray_split(
    array: Sequence[T], max_subarray_length: int, overlap_percentage: float
) -> list[list[T]]:
    assert max_subarray_length > 0, "max_subarray_length must be positive"
    assert 0 <= overlap_percentage < 1, "overlap_percentage must be in [0, 1)"
    if len(array) <= max_subarray_length:
        return [list(array)]

    desired_overlap = math.floor(max_subarray_length * overlap_percentage)
    max_overlap_items = min(max_subarray_length - 1, max_subarray_length // 2)
    overlap_items = min(desired_overlap, max_overlap_items)

    step = max_subarray_length - overlap_items
    step = max(1, step)

    subarrays = []
    for start in range(0, len(array), step):
        end = start + max_subarray_length
        subarrays.append(list(array[start:end]))
        if end >= len(array):
            break
    return subarrays


def get_bootstrap_password() -> str:
    if config.bootstrap_password:
        return config.bootstrap_password.get_secret_value()

    password = read_bootstrap_password_file()
    if password is not None:
        return password

    password = generate_bootstrap_password()
    write_bootstrap_password_file(password)
    logger.info(
        "Generated new Clepsy bootstrap password at %s. Retrieve it from the container volume and rotate it after login.",
        config.bootstrap_password_file_path,
    )
    return password


def generate_bootstrap_password() -> str:
    return generate_typable_password(min_entropy_bits=80.0)


def read_bootstrap_password_file() -> str | None:
    path = config.bootstrap_password_file_path

    if not path.is_file():
        return None

    value = path.read_text(encoding="utf-8").strip()
    return value or None


def write_bootstrap_password_file(password: str) -> None:
    path = config.bootstrap_password_file_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(password + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


T = TypeVar("T")


def generate_uuid() -> str:
    return str(uuid4())


def txt(*args: str, join=" ") -> str:
    return join.join(args)


def activity_name_to_id(name: str) -> str:
    ascii_name: str = unidecode(name)
    normalized_name: str = ascii_name.lower().replace(" ", "_")
    cleaned_name: str = re.sub(r"[^a-z0-9_]", "", normalized_name)
    cleaned_name = cleaned_name.strip("_")
    cleaned_name = re.sub(r"_+", "_", cleaned_name)
    return cleaned_name


def resize_image_with_thumbnail(
    image: Image.Image,
    target_width,
    target_height,
    resample_filter: Image.Resampling = Image.Resampling.BICUBIC,
    inplace: bool = True,
) -> Image.Image:
    if image.width <= target_width and image.height <= target_height:
        return image

    if not inplace:
        image = image.copy()
    # Resize using the thumbnail method
    image.thumbnail((target_width, target_height), resample=resample_filter)

    image.thumbnail((target_width, target_height), resample=resample_filter)
    return image


TRANS_TABLE = str.maketrans(
    {
        "-": "",
        "_": "",
        ".": "",
        ",": "",
        "(": "",
        ")": "",
        "[": "",
        "]": "",
        "{": "",
        "}": "",
        "/": "",
        "\\": "",
        "|": "",
        ":": "",
        ";": "",
        "'": "",
        '"': "",
        "`": "",
        "\t": "",
        "\n": "",
        "\r": "",
    }
)


def pil_image_to_base64(image: Image.Image, img_format: str = "PNG") -> str:
    buffered = io.BytesIO()
    image.save(buffered, format=img_format)
    img_str = base64.b64encode(buffered.getvalue())
    return img_str.decode("utf-8")


def pil_image_to_baml(image: Image.Image) -> BamlImage:
    b64 = pil_image_to_base64(image, img_format="PNG")
    return BamlImage.from_base64(base64=b64, media_type="image/png")


def datetime_to_iso_8601(dt: datetime, include_tz: bool = False) -> str:
    if include_tz:
        return dt.isoformat()
    else:
        return dt.replace(tzinfo=None).isoformat()


def custom_template(pattern: str) -> Callable[[str, dict], str]:
    compiled_pattern = re.compile(pattern)

    def substitute(text: str, values: dict) -> str:
        return compiled_pattern.sub(lambda m: str(values[m.group(1)]), text)

    return substitute


substitute_template = custom_template(r"\[\[\$(\w+)\]\]")


def dates_equal_to_minute(date1: datetime, date2: datetime) -> bool:
    return date1.replace(second=0, microsecond=0) == date2.replace(
        second=0, microsecond=0
    )


def check_activity_events(
    events: list[ActivityEvent],
    activity_completed: bool | None = None,
) -> CheckWithError:
    sorted_events = sorted(events, key=lambda e: e.event_time)
    n_events = len(sorted_events)

    if n_events == 0:
        return CheckWithError(
            False,
            "No events provided",
        )

    # First event must be OPEN
    if sorted_events[0].event_type != ActivityEventType.OPEN:
        return CheckWithError(
            False,
            "First event must be an OPEN event",
        )

    # Events must alternate between OPEN and CLOSE
    for index, event in enumerate(sorted_events):
        event_type = event.event_type
        is_first = index == 0
        is_last = index == n_events - 1

        if is_first:
            # Already checked above
            continue

        previous_event_type = sorted_events[index - 1].event_type

        # Events must alternate: OPEN -> CLOSE -> OPEN -> CLOSE
        if previous_event_type == ActivityEventType.OPEN:
            if event_type != ActivityEventType.CLOSE:
                return CheckWithError(
                    False,
                    f"OPEN event must be followed by CLOSE event, got {event_type}",
                )
        elif previous_event_type == ActivityEventType.CLOSE:
            if event_type != ActivityEventType.OPEN:
                return CheckWithError(
                    False,
                    f"CLOSE event must be followed by OPEN event, got {event_type}",
                )

        # Validate event type is valid
        if event_type not in [ActivityEventType.OPEN, ActivityEventType.CLOSE]:
            return CheckWithError(
                False,
                f"Invalid event type: {event_type}",
            )

        # If activity is completed, last event must be CLOSE
        if is_last and activity_completed and event_type != ActivityEventType.CLOSE:
            return CheckWithError(
                False,
                "Last event must be a CLOSE event for completed activities",
            )

    return CheckWithError(True, None)


def format_date_with_ordinal(d: datetime_date) -> str:
    day = d.day
    if 11 <= day <= 13:
        suffix = "th"
    else:
        suffixes = {1: "st", 2: "nd", 3: "rd"}
        suffix = suffixes.get(day % 10, "th")

    return f"{day}{suffix} {d.strftime('%B %Y')}"


def tzinfo_from_str(tz: str):
    try:
        return ZoneInfo(tz)
    except ZoneInfoNotFoundError:
        return timezone.utc


def to_local(dt: datetime, tz_str: str) -> datetime:
    tzinfo = tzinfo_from_str(tz_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tzinfo)


def format_recent_or_ordinal(
    dt: datetime | None, tz_str: str, *, now: datetime | None = None
) -> str:
    if dt is None:
        return "-"
    if now is None:
        now = datetime.now(timezone.utc)
    base = dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
    delta = now - base.astimezone(timezone.utc)
    total_seconds = int(max(delta.total_seconds(), 0))
    if total_seconds >= 86400:
        local = to_local(dt, tz_str)
        return format_date_with_ordinal(local.date())
    hours, rem = divmod(total_seconds, 3600)
    if hours > 0:
        minutes = rem // 60
        return f"{hours}h {minutes}m"
    minutes, seconds = divmod(rem, 60)
    if minutes > 0:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def datetime_to_start_of_day(dt: datetime) -> datetime:
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def datetime_to_end_of_day(dt: datetime) -> datetime:
    return datetime_to_start_of_day(dt) + timedelta(days=1)


def datetime_to_end_of_week(dt: datetime) -> datetime:
    start_of_day = datetime_to_start_of_day(dt)
    days_ahead = 7 - start_of_day.weekday()
    if days_ahead == 0:
        days_ahead = 7
    return start_of_day + timedelta(days=days_ahead)


def datetime_to_end_of_month(dt: datetime) -> datetime:
    start_of_day = datetime_to_start_of_day(dt)
    if start_of_day.month == 12:
        return start_of_day.replace(year=start_of_day.year + 1, month=1, day=1)
    else:
        return start_of_day.replace(month=start_of_day.month + 1, day=1)


def calculate_date_based_on_view_mode(
    reference_date: datetime,
    view_mode: ViewMode,
    offset: int,
) -> tuple[datetime, datetime]:
    reference_date = datetime_to_start_of_day(reference_date)

    match view_mode:
        case ViewMode.DAILY:
            start = reference_date + timedelta(days=offset)
            end = start + timedelta(days=1)
            return start, end

        case ViewMode.WEEKLY:
            ref = reference_date + timedelta(weeks=offset)
            start = ref - timedelta(days=ref.weekday())
            end = start + timedelta(days=7)  # exclusive
            return start, end

        case ViewMode.MONTHLY:
            # Always start from the beginning of the month for monthly calculations
            reference_date = reference_date.replace(day=1)

            start = reference_date + relativedelta(months=offset)
            end = start + relativedelta(months=1)  # exclusive
            return start, end

        case _:
            raise ValueError("Unsupported view mode")
