from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import aiosqlite
from dramatiq.errors import DramatiqError
from htpy import Element, div, h2, p, span

from clepsy.db.queries import (
    select_goal_progress_current,
    select_goals_with_latest_definition,
    select_last_goal_results_for_goal,
    select_user_settings,
)
from clepsy.entities import (
    GoalMetric,
    GoalWithLatestResult,
)
from clepsy.frontend.components import (
    create_button,
    create_popover,
    create_standard_content,
)
from clepsy.frontend.components.icons import get_icon_svg
from clepsy.jobs.goals import run_update_current_progress_job
from clepsy.modules.goals.calculate_goals import (
    is_progress_stale,
)

from .utils import (
    complete_periods_since_created,
    format_duration_value,
    format_productivity_value,
    friendly_metric_name,
    friendly_period_name,
    operator_symbol,
)


async def create_goals_page(conn: aiosqlite.Connection) -> Element:
    """Creates the goals page listing goals as horizontal cards."""
    user_settings = await select_user_settings(conn)
    assert user_settings is not None, "User settings not found"

    goals = await select_goals_with_latest_definition(conn, last_successes_limit=8)

    header = div(
        class_="p-6 border-b border-outline flex items-center justify-between gap-4"
    )[
        div[
            h2(
                class_="text-lg font-semibold text-on-surface-strong dark:text-on-surface-dark-strong"
            )["Goals"],
            p(class_="text-sm text-muted-foreground")[
                "Manage your goals and see latest results."
            ],
        ],
        create_button(
            text="Add Goal",
            variant="primary",
            attrs={
                "onclick": "window.location.href='/s/goals/create-goal'",
            },
        ),
    ]

    if not goals:
        body = div(class_="p-6")[
            p(class_="text-sm text-muted-foreground")["No goals created yet."]
        ]
        content_card = div(class_="card")[header, body]
        return create_standard_content(
            user_settings=user_settings, content=[content_card]
        )

    # Build a vertical list of horizontal goal cards
    row_tasks = [render_goal_row(conn, g) for g in goals]
    rows = await asyncio.gather(*row_tasks)

    body = div(class_="p-4 space-y-4")[*rows]

    content_card = div(class_="card")[header, body]

    return create_standard_content(
        user_settings=user_settings,
        content=[content_card],
    )


async def render_goal_row(
    conn: aiosqlite.Connection,
    gwr: GoalWithLatestResult,
    ttl_from_db: timedelta = timedelta(seconds=60),
) -> Element:
    # using div, span, create_button, create_popover from outer scope imports

    goal = gwr.goal
    definition = gwr.definition
    metric_label = friendly_metric_name(goal.metric)
    period_label = friendly_period_name(goal.period)

    # Fetch current progress and history
    progress_row = await select_goal_progress_current(
        conn, goal_definition_id=definition.id
    )
    hist = await select_last_goal_results_for_goal(conn, goal_id=goal.id, limit=5)
    now_utc = datetime.now(timezone.utc)
    ttl_seconds = 60
    stale = is_progress_stale(
        progress_row.updated_at if progress_row else None, now_utc, ttl_seconds
    )
    is_active = goal.paused_since is None

    # Build history timeline
    all_periods = complete_periods_since_created(
        goal.period, goal.timezone, goal.created_at, now_utc
    )
    periods = list(reversed(all_periods[-5:]))
    hist_map = {(r.period_start, r.period_end): r for r in hist}

    # Precompute timeline elems for assembly
    timeline_elems = []
    for start, end in periods:
        r = hist_map.get((start, end))
        if r is None:
            timeline_elems.append(span(class_="text-muted-foreground")["—"])
        else:
            if (
                str(r.eval_state) == "paused"
                or getattr(r, "eval_state", None) == "paused"
            ):
                timeline_elems.append(
                    span(class_="text-amber-500")[get_icon_svg("pause")]
                )
            elif r.success is None:
                timeline_elems.append(span(class_="text-muted-foreground")["—"])
            else:
                timeline_elems.append(
                    span(class_="text-green-600")[get_icon_svg("tick")]
                    if bool(r.success)
                    else span(class_="text-red-600")[get_icon_svg("x")]
                )
    has_periods = bool(periods)

    # Kick background refresh via Dramatiq if stale or no current progress
    if is_active and (stale or progress_row is None):
        try:
            run_update_current_progress_job.send(
                goal.id, float(ttl_from_db.total_seconds())
            )
        except DramatiqError:
            # Best-effort enqueue; UI will keep polling/allow manual refresh
            pass

    # Assemble card
    created_local = goal.created_at.astimezone(ZoneInfo(goal.timezone))
    created_date_str = created_local.strftime("%Y-%m-%d")
    root_attrs = {"id": f"goal-row-{goal.id}", "class_": "card"}
    if is_active and stale:
        root_attrs.update(
            {
                "hx-get": f"/s/goals/row/{goal.id}",
                "hx-trigger": "load, every 3s",
                "hx-target": f"#goal-row-{goal.id}",
                "hx-swap": "outerHTML",
            }
        )

    refresh_btn = create_button(
        text=None,
        variant="secondary",
        icon="refresh",
        attrs={
            "type": "button",
            "hx-get": f"/s/goals/row/{goal.id}/refresh",
            "hx-target": f"#goal-row-{goal.id}",
            "hx-swap": "outerHTML",
        },
    )

    # Inline play button when goal is paused (old behavior)
    play_btn = None
    if not is_active:
        play_btn = create_button(
            text=None,
            variant="secondary",
            icon="play",
            attrs={
                "type": "button",
                "title": "Resume goal",
                "hx-put": f"/s/goals/{goal.id}/pause-toggle",
                "hx-vals": '{"enabled": true}',
                "hx-target": f"#goal-row-{goal.id}",
                "hx-swap": "outerHTML",
            },
        )

    # Metric-specific current/target labels
    if goal.metric == GoalMetric.AVG_PRODUCTIVITY_LEVEL:
        current_value = format_productivity_value(
            progress_row.metric_value if progress_row else None  # type: ignore[attr-defined]
        )
        target_value_text = format_productivity_value(definition.target_value)  # type: ignore[arg-type]
    else:
        current_value = format_duration_value(
            progress_row.metric_value if progress_row else None  # type: ignore[attr-defined]
        )
        target_value_text = format_duration_value(definition.target_value)  # type: ignore[arg-type]

    full_target_text = (
        f"{metric_label} {operator_symbol(goal.operator)} {target_value_text}"
    )

    # create_popover already imported above

    return div(**root_attrs)[
        # Header: Name + meta badges | Controls
        div(class_="p-4 pb-3 flex items-start justify-between gap-6")[
            div(class_="min-w-0 space-y-1")[
                div(
                    class_="text-base font-medium text-on-surface-strong dark:text-on-surface-dark-strong truncate"
                )[definition.name],
                div(class_="text-[10px] text-muted-foreground flex items-center gap-2")[
                    span(class_="px-1.5 py-0.5 rounded bg-muted text-muted-foreground")[
                        metric_label
                    ],
                    span(class_="px-1.5 py-0.5 rounded bg-muted text-muted-foreground")[
                        period_label
                    ],
                ],
            ],
            div(class_="flex items-center gap-2")[
                play_btn,
                create_popover(
                    base_id=f"goal-actions-{goal.id}",
                    trigger_text=None,
                    trigger_variant="secondary",
                    trigger_icon="settings",
                    popover_extra_classes=(
                        "right-0 mt-2 rounded-md border border-outline "
                        "bg-popover text-popover-foreground shadow-lg p-1 space-y-1 absolute"
                    ),
                    wrapper_extra_classes="relative",
                    content=[
                        c
                        for c in [
                            # Edit
                            create_button(
                                text="Edit",
                                variant="ghost",
                                extra_classes="w-full justify-start",
                                attrs={
                                    "type": "button",
                                    "onclick": (
                                        f"window.location.href='/s/goals/{goal.id}/edit'"
                                    ),
                                },
                            ),
                            # Pause/Resume toggle
                            create_button(
                                text=("Pause" if is_active else "Resume"),
                                variant="ghost",
                                extra_classes="w-full justify-start",
                                attrs={
                                    "type": "button",
                                    "title": (
                                        "Pause goal" if is_active else "Resume goal"
                                    ),
                                    "hx-put": f"/s/goals/{goal.id}/pause-toggle",
                                    "hx-vals": (
                                        '{"enabled": false}'
                                        if is_active
                                        else '{"enabled": true}'
                                    ),
                                    "hx-target": f"#goal-row-{goal.id}",
                                    "hx-swap": "outerHTML",
                                },
                            ),
                            # Delete
                            create_button(
                                text="Delete",
                                variant="ghost",
                                extra_classes="w-full justify-start",
                                attrs={
                                    "type": "button",
                                    "title": "Delete goal",
                                    "hx-delete": f"/s/goals/{goal.id}",
                                    "hx-target": f"#goal-row-{goal.id}",
                                    "hx-swap": "delete",
                                    "hx-confirm": "Are you sure you want to delete this goal?",
                                },
                            ),
                        ]
                        if c is not None
                    ],
                ),
            ],
        ],
        # Body: Target | Current period | History
        div(
            class_="px-4 pb-4 pt-0 grid grid-cols-1 sm:grid-cols-3 gap-4 sm:divide-x sm:divide-outline"
        )[
            div(class_="sm:pl-4 flex flex-col gap-2 pt-1")[
                span(
                    class_="text-[10px] uppercase tracking-wide text-muted-foreground"
                )["Target"],
                div(class_="flex items-center text-xs text-muted-foreground")[
                    span[full_target_text],
                ],
            ],
            div(
                class_="sm:pl-4 sm:pr-4 flex flex-col gap-2 pt-1",
                style="padding-right: 1.25rem;",
            )[
                span(
                    class_="text-[10px] uppercase tracking-wide text-muted-foreground"
                )["Current period"],
                div(class_="flex items-center justify-between gap-2")[
                    div(class_="flex items-center gap-3")[
                        span(class_="text-xs text-muted-foreground")["Value"],
                        span(class_="text-sm font-medium text-foreground")[
                            current_value
                        ],
                    ],
                    div(class_="flex items-center")[refresh_btn],
                ],
                div(class_="flex items-center gap-3")[
                    span(class_="text-xs text-muted-foreground")["Goal reached"],
                    (
                        span(class_="text-green-600")[get_icon_svg("tick")]
                        if (progress_row and progress_row.success is True)
                        else span(class_="text-red-600")[get_icon_svg("x")]
                        if (progress_row and progress_row.success is False)
                        else span(class_="text-xs text-muted-foreground")["NA"]
                    ),
                ],
            ],
            div(class_="sm:pl-4 flex flex-col gap-2 pt-1")[
                span(
                    class_="text-[10px] uppercase tracking-wide text-muted-foreground"
                )["History"],
                span(class_="text-[10px] text-muted-foreground")[
                    f"Created {created_date_str}"
                ],
                (
                    span(class_="text-xs text-muted-foreground")["No history yet"]
                    if not has_periods
                    else div(
                        class_="flex items-center gap-2 text-xs text-muted-foreground"
                    )[*timeline_elems]
                ),
            ],
        ],
    ]
