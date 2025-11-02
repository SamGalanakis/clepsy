from __future__ import annotations

from datetime import timedelta

import aiosqlite
from htpy import (
    Element,
    div,
    form,
    h2,
    input as htpy_input,
    label,
    p,
    span,
    template,
)

from clepsy.db.queries import (
    select_tags,
    select_user_settings,
)
from clepsy.entities import (
    GoalMetric,
    GoalPeriod,
    IncludeMode,
    MetricOperator,
    ProductivityLevel,
    avg_productivity_operators,
    total_activity_duration_operators,
)
from clepsy.frontend.components import (
    common_timezones_list,
    create_button,
    create_multiselect,
    create_single_select,
    create_slider,
    create_standard_content,
    create_text_area,
    create_text_input,
    create_time_duration_picker,
    create_time_range,
    create_tooltip,
)

from .utils import friendly_metric_name, metric_slug, operator_label


async def create_create_goal_page(conn: aiosqlite.Connection) -> Element:
    """Initial goal creation page: choose a metric via simple cards."""
    user_settings = await select_user_settings(conn)
    assert user_settings is not None, "User settings not found"

    def metric_card(metric: GoalMetric, title: str, subtitle: str) -> Element:
        return div(
            class_=(
                "transition border rounded-xl bg-card hover:bg-muted cursor-pointer "
                "border-outline px-4 py-3 flex items-center justify-between"
            ),
            role="button",
            tabindex="0",
            **{
                "hx-get": f"/s/goals/create-goal/{metric_slug(metric)}",
                "hx-push-url": "true",
                "hx-target": "#create-goal-container",
                "hx-swap": "outerHTML",
            },
        )[
            div(class_="min-w-0")[
                div(
                    class_="text-sm font-semibold text-on-surface-strong dark:text-on-surface-dark-strong tracking-wide"
                )[title],
                div(class_="text-xs text-muted-foreground truncate")[subtitle],
            ],
            span(class_="text-muted-foreground text-lg")["→"],
        ]

    header = div(class_="p-6 border-b border-outline")[
        h2(
            class_="text-lg font-semibold text-on-surface-strong dark:text-on-surface-dark-strong"
        )["What's your goal?"],
        p(class_="text-sm text-muted-foreground")[
            "Choose the metric that best fits your goal."
        ],
    ]

    body = div(class_="p-4 space-y-3")[
        metric_card(
            GoalMetric.AVG_PRODUCTIVITY_LEVEL,
            "Improve productivity",
            "Aim for an average productivity level over a period.",
        ),
        metric_card(
            GoalMetric.TOTAL_ACTIVITY_DURATION,
            "Focus time goals",
            "Track total focused activity duration for selected tags.",
        ),
    ]

    content_card = div(id="create-goal-container", class_="card")[header, body]
    return create_standard_content(user_settings=user_settings, content=[content_card])


async def create_create_goal_form(
    conn: aiosqlite.Connection, metric: GoalMetric
) -> Element:
    """Render the full create-goal form container for a selected metric."""
    user_settings = await select_user_settings(conn)
    assert user_settings is not None, "User settings not found"

    metric_label = friendly_metric_name(metric)

    # Load tags for filters
    tags = await select_tags(conn)
    tag_options = {t.name: str(t.id) for t in tags if t.id is not None}

    # Allowed operators by metric
    if metric == GoalMetric.AVG_PRODUCTIVITY_LEVEL:
        allowed_ops = avg_productivity_operators
    elif metric == GoalMetric.TOTAL_ACTIVITY_DURATION:
        allowed_ops = total_activity_duration_operators
    else:
        raise ValueError(f"Unsupported metric for goal creation: {metric}")

    # Metric-specific target inputs
    if metric == GoalMetric.AVG_PRODUCTIVITY_LEVEL:
        target_value_ui = create_slider(
            element_id="target_value",
            name="target_value",
            title="Target",
            min_value=0,
            max_value=1,
            step=0.01,
            value=0.70,
            show_value=True,
        )
    elif metric == GoalMetric.TOTAL_ACTIVITY_DURATION:
        target_value_ui = div(class_="space-y-2")[
            label(class_="label")["Target duration"],
            create_time_duration_picker(
                element_id="target_seconds",
                name="target_seconds",
                title=None,
                include_seconds=False,
                min_duration=timedelta(minutes=1),
                max_duration=timedelta(hours=99, minutes=59),
                initial_duration=timedelta(minutes=30),
            ),
            p(class_="text-xs text-muted-foreground")[
                "Format HH:MM (e.g., 01:30 for 1h 30m)."
            ],
        ]
    else:
        raise ValueError(
            f"Unsupported metric for goal creation: {metric}. "
            "Only AVG_PRODUCTIVITY_LEVEL and TOTAL_ACTIVITY_DURATION are supported."
        )

    # Period radios
    period_ui = div(class_="space-y-2")[
        label(class_="label")["Period"],
        div(class_="flex items-center gap-6")[
            label(class_="inline-flex items-center gap-2 input")[
                htpy_input(
                    type="radio",
                    name="period",
                    value=GoalPeriod.DAY.value,
                    checked=True,
                    class_="input",
                ),
                span["Day"],
            ],
            label(class_="inline-flex items-center gap-2 input")[
                htpy_input(type="radio", name="period", value=GoalPeriod.WEEK.value),
                span["Week"],
            ],
            label(class_="inline-flex items-center gap-2 input")[
                htpy_input(type="radio", name="period", value=GoalPeriod.MONTH.value),
                span["Month"],
            ],
        ],
    ]

    days = [
        ("Mon", "monday"),
        ("Tue", "tuesday"),
        ("Wed", "wednesday"),
        ("Thu", "thursday"),
        ("Fri", "friday"),
        ("Sat", "saturday"),
        ("Sun", "sunday"),
    ]

    header = div(class_="p-6 border-b border-outline")[
        h2(
            class_="text-lg font-semibold text-on-surface-strong dark:text-on-surface-dark-strong"
        )[f"Create Goal — {metric_label}"],
        p(class_="text-sm text-muted-foreground")["Fill in the details below."],
    ]

    match metric:
        case GoalMetric.AVG_PRODUCTIVITY_LEVEL:
            default_operator = MetricOperator.GREATER_THAN
        case GoalMetric.TOTAL_ACTIVITY_DURATION:
            default_operator = MetricOperator.LESS_THAN
        case _:
            raise ValueError(f"Unsupported metric for goal creation: {metric}")

    form_body = div(class_="p-6 space-y-6")[
        div(class_="grid gap-4")[
            create_text_input(
                element_id="goal_name",
                name="name",
                title="Name",
                placeholder="e.g., Daily Focus Time",
                required=True,
                attrs={"type": "text"},
            ),
            create_text_area(
                element_id="goal_description",
                name="description",
                title="Description",
                placeholder="Optional description",
            ),
            create_single_select(
                element_id="timezone",
                include_search=True,
                name="timezone",
                title="Timezone",
                options={tz: tz for tz in common_timezones_list},
                selected_val=user_settings.timezone,
            ),
        ],
        div(class_="card p-4 space-y-3")[
            h2(class_="text-sm font-semibold text-on-surface-strong")["Target"],
            create_single_select(
                element_id="operator",
                name="operator",
                title="Operator",
                options={operator_label(op): op.value for op in allowed_ops},
                selected_val=default_operator.value,
            ),
            target_value_ui,
            period_ui,
        ],
        div(class_="card p-4 space-y-5")[
            h2(class_="text-sm font-semibold text-on-surface-strong")["Filters"],
            div(class_="space-y-2")[
                div(class_="mb-4")[
                    create_single_select(
                        element_id="include_mode",
                        name="include_mode",
                        title="Include tags mode",
                        options={
                            "Any of these": IncludeMode.ANY.value,
                            "All of these": IncludeMode.ALL.value,
                        },
                        selected_val=IncludeMode.ANY.value,
                    )
                ],
                div(class_="flex justify-end !overflow-visible")[
                    create_tooltip(
                        button_text="i",
                        tooltip_text=(
                            "Activities must match these tags (combined with mode)."
                        ),
                    )
                ],
                create_multiselect(
                    element_id="include_tags",
                    name="include_tag_ids",
                    title="Include tags",
                    label_to_val=tag_options,
                    selected_labels=[],
                ),
            ],
            div(class_="space-y-2")[
                div(class_="flex items-center justify-between")[
                    label(class_="label")["Days of week"],
                    div(class_="flex justify-end !overflow-visible")[
                        create_tooltip(
                            button_text="i",
                            tooltip_text="Limit evaluation to selected days.",
                        )
                    ],
                ],
                div(class_="flex flex-wrap gap-4")[
                    *[
                        label(class_="inline-flex items-center gap-2")[
                            htpy_input(
                                type="checkbox", name="days[]", value=val, checked=True
                            ),
                            span[text],
                        ]
                        for text, val in days
                    ]
                ],
            ],
            div(class_="space-y-2")[
                div(class_="flex justify-end !overflow-visible")[
                    create_tooltip(
                        button_text="i",
                        tooltip_text="Activities with these tags will be ignored.",
                    )
                ],
                create_multiselect(
                    element_id="exclude_tags",
                    name="exclude_tag_ids",
                    title="Exclude tags",
                    label_to_val=tag_options,
                    selected_labels=[],
                ),
            ],
            div(class_="space-y-2")[
                div(class_="flex justify-end !overflow-visible")[
                    create_tooltip(
                        button_text="i",
                        tooltip_text=(
                            "Only activities whose productivity level is one of the selected values will be considered."
                        ),
                    )
                ],
                create_multiselect(
                    element_id="productivity_levels",
                    name="productivity_levels[]",
                    title="Productivity levels",
                    label_to_val={
                        "Very productive": ProductivityLevel.VERY_PRODUCTIVE.value,
                        "Productive": ProductivityLevel.PRODUCTIVE.value,
                        "Neutral": ProductivityLevel.NEUTRAL.value,
                        "Distracting": ProductivityLevel.DISTRACTING.value,
                        "Very distracting": ProductivityLevel.VERY_DISTRACTING.value,
                    },
                    selected_labels=[],
                ),
            ],
            div(
                class_="space-y-2",
                x_data=(
                    "{ add() { let t = document.getElementById('time-range-template'); "
                    "let c = t.content.cloneNode(true); document.getElementById('time-range-list').appendChild(c); } }"
                ),
            )[
                div(class_="flex items-center justify-between")[
                    label(class_="label")["Time of day"],
                    div(class_="flex items-center gap-2")[
                        div(class_="flex justify-end !overflow-visible")[
                            create_tooltip(
                                button_text="i",
                                tooltip_text="Only count activity within these time ranges.",
                            )
                        ],
                        create_button(
                            text=None,
                            variant="secondary",
                            icon="plus",
                            attrs={"type": "button", "@click": "add()"},
                        ),
                    ],
                ],
                template(id="time-range-template")[
                    div(class_="flex items-center gap-2")[
                        create_time_range(
                            start_id="time_start",
                            start_name="time_starts[]",
                            end_id="time_end",
                            end_name="time_ends[]",
                            title="",
                            placeholder_start="Start",
                            placeholder_end="End",
                            time_24hr=True,
                        ),
                        create_button(
                            text="",
                            variant="secondary",
                            icon="delete",
                            attrs={
                                "type": "button",
                                "@click": "$el.parentElement.remove()",
                            },
                        ),
                    ]
                ],
                div(id="time-range-list", class_="space-y-2")[""],
            ],
        ],
    ]

    the_form = div(id="create-goal-container", class_="card")[
        header,
        form(
            id="create-goal-form",
            method="POST",
            **{
                "hx-post": f"/s/goals/create-goal/submit/{metric_slug(metric)}",
                "hx-target": "#create-goal-container",
                "hx-swap": "outerHTML",
            },
        )[
            htpy_input(type="hidden", name="metric", value=metric.value),
            form_body,
            div(
                class_="p-4 border-t border-outline flex items-center justify-end gap-3"
            )[
                create_button(
                    text="Cancel",
                    variant="secondary",
                    attrs={
                        "hx-get": "/s/goals/create-goal",
                        "hx-push-url": "true",
                        "hx-target": "#content",
                        "hx-swap": "outerHTML",
                    },
                ),
                create_button(
                    text="Submit",
                    variant="primary",
                    attrs={"type": "submit"},
                ),
            ],
        ],
    ]

    return the_form


async def create_create_goal_form_page(
    conn: aiosqlite.Connection, metric: GoalMetric
) -> Element:
    """Wrap the metric-specific form container in standard content for full page."""
    user_settings = await select_user_settings(conn)
    assert user_settings is not None, "User settings not found"

    form_container = await create_create_goal_form(conn=conn, metric=metric)
    return create_standard_content(
        user_settings=user_settings, content=[form_container]
    )
