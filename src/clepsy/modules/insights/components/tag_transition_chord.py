from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from typing import Any, List

from htpy import div, script

from clepsy import utils


DBActivitySpecWithTags = Any


MAX_TAGS = 10


@dataclass
class _TagInfo:
    id: int
    name: str
    count: int


def _clamp_interval(
    start: datetime, end: datetime, window_start: datetime, window_end: datetime
) -> tuple[datetime, datetime] | None:
    if end <= window_start or start >= window_end:
        return None
    clamped_start = start if start >= window_start else window_start
    clamped_end = end if end <= window_end else window_end
    if clamped_end <= clamped_start:
        return None
    return clamped_start, clamped_end


def _activity_intervals_within_window(
    spec: DBActivitySpecWithTags,
    window_start: datetime,
    window_end: datetime,
) -> list[tuple[datetime, datetime]]:
    events = sorted(spec.events, key=lambda e: e.event_time)
    intervals: list[tuple[datetime, datetime]] = []
    open_time: datetime | None = None

    for event in events:
        if event.event_type == "open":
            open_time = event.event_time
        elif event.event_type == "close" and open_time:
            clamped = _clamp_interval(
                open_time, event.event_time, window_start, window_end
            )
            if clamped:
                intervals.append(clamped)
            open_time = None

    if open_time:
        clamped = _clamp_interval(open_time, window_end, window_start, window_end)
        if clamped:
            intervals.append(clamped)

    intervals.sort(key=lambda pair: pair[0])
    return intervals


def _collect_active_specs(
    specs: List[DBActivitySpecWithTags],
    window_start: datetime,
    window_end: datetime,
) -> list[tuple[DBActivitySpecWithTags, list[tuple[datetime, datetime]]]]:
    active: list[tuple[DBActivitySpecWithTags, list[tuple[datetime, datetime]]]] = []
    for spec in specs:
        intervals = _activity_intervals_within_window(spec, window_start, window_end)
        if intervals:
            active.append((spec, intervals))
    return active


def _select_top_tags(
    active_specs: list[tuple[DBActivitySpecWithTags, list[tuple[datetime, datetime]]]],
) -> list[_TagInfo]:
    freq: dict[int, _TagInfo] = {}
    for spec, _ in active_specs:
        seen = set()
        for tag in spec.tags:
            # Avoid double-counting a tag repeated (shouldn't happen but safe)
            if tag.id in seen:
                continue
            seen.add(tag.id)
            if tag.id not in freq:
                freq[tag.id] = _TagInfo(id=tag.id, name=tag.name, count=0)
            freq[tag.id].count += 1
    # Order by frequency desc then name
    ordered = sorted(freq.values(), key=lambda t: (-t.count, t.name.lower()))
    return ordered[:MAX_TAGS]


def _build_transition_matrix(
    active_specs: list[tuple[DBActivitySpecWithTags, list[tuple[datetime, datetime]]]],
    top_tags: list[_TagInfo],
):
    if not top_tags:
        return [], []
    index = {t.id: i for i, t in enumerate(top_tags)}
    size = len(top_tags)
    matrix = [[0 for _ in range(size)] for _ in range(size)]

    # Sort specs by first event time (start)
    indexed_specs = [
        (idx, spec, intervals) for idx, (spec, intervals) in enumerate(active_specs)
    ]
    ordered_specs = sorted(
        indexed_specs,
        key=lambda item: (
            item[2][0][0],
            item[0],
        ),
    )
    if len(ordered_specs) < 2:
        return matrix, top_tags

    prev_spec = ordered_specs[0][1]
    for _, cur_spec, _ in ordered_specs[1:]:
        prev_tag_ids = [t.id for t in prev_spec.tags if t.id in index]
        cur_tag_ids = [t.id for t in cur_spec.tags if t.id in index]
        if prev_tag_ids and cur_tag_ids:
            for a in prev_tag_ids:
                for b in cur_tag_ids:
                    matrix[index[a]][index[b]] += 1
        prev_spec = cur_spec
    return matrix, top_tags


def build_tag_transition_payload(
    specs: List[DBActivitySpecWithTags],
    *,
    start_time_user_tz: datetime,
    end_time_user_tz: datetime,
):
    active_specs = _collect_active_specs(specs, start_time_user_tz, end_time_user_tz)
    top_tags = _select_top_tags(active_specs)
    matrix, tags = _build_transition_matrix(active_specs, top_tags)
    total_unique_tags = {tag.id for spec, _ in active_specs for tag in spec.tags}
    return json.dumps(
        {
            "tags": [{"id": t.id, "name": t.name, "count": t.count} for t in tags],
            "matrix": matrix,
            "total_tag_count": len(total_unique_tags),
            "start_date": utils.datetime_to_iso_8601(start_time_user_tz),
            "end_date": utils.datetime_to_iso_8601(end_time_user_tz),
        }
    )


def create_tag_transition_chord_body(
    specs: List[DBActivitySpecWithTags],
    *,
    start_time_user_tz: datetime,
    end_time_user_tz: datetime,
):
    payload = build_tag_transition_payload(
        specs,
        start_time_user_tz=start_time_user_tz,
        end_time_user_tz=end_time_user_tz,
    )
    return div(
        id="tag_transition_chord_chart",
        # Provide both min width (for chord readability) and min height so wrapper sizing can grow vertically.
        # Allow vertical overflow (labels) while constraining horizontal overflow to prevent flex width creep.
        # Responsive square container:
        # - aspect-square keeps the chord truly circular and avoids vertical clipping logic.
        # - max-w tiers constrain runaway width on very large screens while still letting it fill small ones.
        # - min-w/min-h 320 preserve baseline readability; larger datasets still adapt via internal padding logic.
        # - overflow-visible allows labels to render fully (margins aim to keep them inside, but safety).
        # - mx-auto centers the square within the wrapper when wrapper wider than max-w.
        # NOTE: Wrapper still has flex sizing; this inner container governs actual measured width/height for the chart.
        class_=(
            "lg:max-w-[800px] xl:max-w-[900px] 2xl:max-w-[1000px] min-w-[320px] min-h-[320px] "
        ),
        x_init="window.initTagTransitionChordFromJson($el.dataset.tagchord)",
        **{"data-tagchord": payload},
    )


def create_tag_transition_chord_container(
    specs: List[DBActivitySpecWithTags],
    *,
    start_time_user_tz: datetime,
    end_time_user_tz: datetime,
):
    body = create_tag_transition_chord_body(
        specs,
        start_time_user_tz=start_time_user_tz,
        end_time_user_tz=end_time_user_tz,
    )
    return div(
        id="tag-transition-chord-wrapper",
        class_="insight-graph w-full min-w-0",
        **{
            "hx-get": "/s/insights/update-tag-transition-chord",
            "hx-trigger": "update_insights_diagrams from:body",
            "hx-target": "#tag_transition_chord_chart",
            "hx-swap": "outerHTML",
            "x-bind:hx-vals": (
                "JSON.stringify({reference_date: reference_date, view_mode: view_mode, offset: offset, selected_tag_ids: JSON.stringify(selected_tag_ids)})"
            ),
        },
    )[
        # Script depends only on global d3
        script(src="/static/custom_scripts/insights_tag_transition_chord.js"),
        body,
    ]
