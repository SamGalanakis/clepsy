from __future__ import annotations

from datetime import timedelta

import aiosqlite
from htpy import Element, div, form, h2, input as htpy_input, label, p, span, template

from clepsy.db.queries import (
    select_goals_with_latest_definition,
    select_tags,
    select_user_settings,
)
from clepsy.entities import (
    DaysOfWeek,
    GoalMetric,
    IncludeMode,
    ProductivityLevel,
)
from clepsy.frontend.components import (
    create_button,
    create_multiselect,
    create_single_select,
    create_standard_content,
    create_text_area,
    create_text_input,
    create_time_duration_picker,
    create_time_range,
    create_tooltip,
)

from .utils import (
    friendly_metric_name,
    friendly_period_name,
    metric_slug,
    operator_label,
)


async def create_edit_goal_page(
    conn: aiosqlite.Connection,
    goal_id: int,
    *,
    name_error: str | None = None,
    description_error: str | None = None,
    include_mode_error: str | None = None,
    metric_params_error: str | None = None,
    target_value_error: str | None = None,
    target_seconds_error: str | None = None,
    name_value: str | None = None,
    description_value: str | None = None,
    include_mode_value: IncludeMode | str | None = None,
    metric_params_value: str | None = None,
    target_value_value: str | None = None,
    target_seconds_value: str | None = None,
    days_value: list[DaysOfWeek] | list[str] | None = None,
    time_pairs_value: list[tuple[str, str]] | None = None,
    productivity_levels_value: list[ProductivityLevel] | list[str] | None = None,
) -> Element:
    """Render the goal edit page with latest definition values prefilled.

    Uneditable fields (metric, operator, period, timezone) are shown for context but not in the form.
    """
    user_settings = await select_user_settings(conn)
    assert user_settings is not None, "User settings not found"

    gwrs = await select_goals_with_latest_definition(conn, last_successes_limit=1)
    gwr = next((g for g in gwrs if g.goal.id == goal_id), None)
    assert gwr is not None, "Goal not found"

    goal = gwr.goal
    d = gwr.definition

    # Prefill values
    name_val = name_value if name_value is not None else d.name
    desc_val = (
        description_value if description_value is not None else (d.description or "")
    )
    include_mode_val = (
        include_mode_value.value
        if isinstance(include_mode_value, IncludeMode)
        else include_mode_value
        if include_mode_value is not None
        else d.include_mode.value
    )
    metric_params_val = metric_params_value or ""

    # Target depends on metric
    if goal.metric == GoalMetric.AVG_PRODUCTIVITY_LEVEL:
        target_val = (
            target_value_value
            if target_value_value is not None
            else str(d.target_value)
        )
    else:
        minutes = int(d.target_value.total_seconds() // 60)  # type: ignore[attr-defined]
        target_val = (
            target_seconds_value if target_seconds_value is not None else str(minutes)
        )

    # Filters
    days_selected = days_value if days_value is not None else (d.day_filter or [])
    time_pairs = (
        time_pairs_value if time_pairs_value is not None else (d.time_filter or [])
    )
    if productivity_levels_value is not None:
        prod_levels = [
            pl.value if isinstance(pl, ProductivityLevel) else pl
            for pl in productivity_levels_value
        ]
    else:
        prod_levels = [pl.value for pl in (d.productivity_filter or [])]

    # Build UI
    header = div(class_="p-6 border-b border-outline")[
        h2(class_="text-lg font-semibold text-on-surface-strong")["Edit Goal"],
        p(class_="text-sm text-muted-foreground")[
            "Update goal details. Non-editable settings are shown for context."
        ],
    ]

    # Uneditable context
    context_card = div(
        class_="card p-4 mb-4 text-sm text-muted-foreground space-y-2 relative"
    )[
        div(class_="absolute top-2 right-2 !overflow-visible")[
            create_tooltip(
                button_text="i",
                tooltip_text=(
                    "These settings can’t be edited to preserve continuity of historical results. "
                    "To change them, create a new goal."
                ),
                side="left",
                align="center",
                extra_classes="btn-ghost btn-icon text-muted-foreground",
                attrs={"aria-label": "Why are these settings frozen?"},
            ),
        ],
        div()[
            span(class_="font-medium text-foreground")["Metric:"],
            " ",
            friendly_metric_name(goal.metric),
        ],
        div()[
            span(class_="font-medium text-foreground")["Operator:"],
            " ",
            operator_label(goal.operator),
        ],
        div()[
            span(class_="font-medium text-foreground")["Period:"],
            " ",
            friendly_period_name(goal.period),
        ],
        div()[
            span(class_="font-medium text-foreground")["Timezone:"], " ", goal.timezone
        ],
    ]

    include_mode_options = {
        "Any of these": IncludeMode.ANY.value,
        "All of these": IncludeMode.ALL.value,
    }

    tags = await select_tags(conn)
    tag_options = {t.name: str(t.id) for t in tags if t.id is not None}

    time_template = template(id="edit-time-range-template")[
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
                icon="plus",
                attrs={"type": "button", "@click": "$el.parentElement.remove()"},
            ),
        ]
    ]

    target_block_children: list[Element] = []
    include_metric_params = False
    if goal.metric == GoalMetric.AVG_PRODUCTIVITY_LEVEL:
        target_block_children = [
            create_single_select(
                element_id="include_mode",
                name="include_mode",
                title="Include tags mode",
                options=include_mode_options,
                selected_val=include_mode_val,
            ),
        ]
        if include_mode_error:
            target_block_children.append(
                p(class_="text-destructive text-sm")[include_mode_error]
            )
        target_block_children.append(
            create_text_input(
                element_id="target_value",
                name="target_value",
                title="Target (0.00 – 1.00)",
                placeholder="0.70",
                value=target_val,
                attrs={"type": "number", "step": "0.01"},
            )
        )
        if target_value_error:
            target_block_children.append(
                p(class_="text-destructive text-sm")[target_value_error]
            )
        include_metric_params = False
    elif goal.metric == GoalMetric.TOTAL_ACTIVITY_DURATION:
        init_seconds: int = int(d.target_value.total_seconds())  # type: ignore[attr-defined]
        posted_seconds = target_seconds_value or target_value_value
        if isinstance(posted_seconds, str) and posted_seconds.strip():
            try:
                init_seconds = int(float(posted_seconds))
            except (TypeError, ValueError):
                pass
        init_duration = timedelta(seconds=init_seconds or (30 * 60))

        target_block_children = [
            create_single_select(
                element_id="include_mode",
                name="include_mode",
                title="Include tags mode",
                options=include_mode_options,
                selected_val=include_mode_val,
            ),
            create_time_duration_picker(
                element_id="edit_target_seconds",
                name="target_seconds",
                title="Target duration",
                include_seconds=False,
                min_duration=timedelta(minutes=1),
                max_duration=timedelta(hours=99, minutes=59),
                initial_duration=init_duration,
            ),
        ]
        if include_mode_error:
            target_block_children.append(
                p(class_="text-destructive text-sm")[include_mode_error]
            )
        if target_seconds_error:
            target_block_children.append(
                p(class_="text-destructive text-sm")[target_seconds_error]
            )
        elif target_value_error:
            target_block_children.append(
                p(class_="text-destructive text-sm")[target_value_error]
            )
        include_metric_params = False
    else:
        target_block_children = [
            create_single_select(
                element_id="include_mode",
                name="include_mode",
                title="Include tags mode",
                options=include_mode_options,
                selected_val=include_mode_val,
            ),
            create_text_input(
                element_id="target_value",
                name="target_value",
                title="Target",
                placeholder="",
                value=target_val,
                attrs={"type": "number", "step": "0.01"},
            ),
        ]
        if include_mode_error:
            target_block_children.append(
                p(class_="text-destructive text-sm")[include_mode_error]
            )
        if target_value_error:
            target_block_children.append(
                p(class_="text-destructive text-sm")[target_value_error]
            )
        include_metric_params = True

    metric_params_block = (
        [
            create_text_area(
                element_id="metric_params",
                name="metric_params",
                title="Metric parameters (JSON, optional)",
                placeholder="{}",
                value=metric_params_val,
                rows=3,
            ),
            (
                p(class_="text-destructive text-sm")[metric_params_error]
                if metric_params_error
                else None
            ),
        ]
        if include_metric_params
        else []
    )

    form_body = div(class_="card p-6 space-y-6")[
        h2(class_="text-lg font-semibold text-on-surface-strong")["General"],
        div(class_="grid gap-3")[
            create_text_input(
                element_id="name",
                name="name",
                title="Name",
                placeholder="Goal name",
                value=name_val,
                attrs={"type": "text"},
                valid_state=(name_error is None),
            ),
            (p(class_="text-destructive text-sm")[name_error] if name_error else None),
            create_text_area(
                element_id="description",
                name="description",
                title="Description",
                placeholder="Optional description",
                value=desc_val,
            ),
            (
                p(class_="text-destructive text-sm")[description_error]
                if description_error
                else None
            ),
        ],
        div(class_="card p-4 space-y-3")[
            h2(class_="text-sm font-semibold text-on-surface-strong")["Target"],
            *target_block_children,
            *metric_params_block,
        ],
        div(class_="card p-4 space-y-5")[
            h2(class_="text-sm font-semibold text-on-surface-strong")["Filters"],
            create_multiselect(
                element_id="include_tags",
                name="include_tag_ids",
                title="Include tags",
                label_to_val=tag_options,
                selected_labels=[t.name for t in gwr.include_tags],
            ),
            create_multiselect(
                element_id="exclude_tags",
                name="exclude_tag_ids",
                title="Exclude tags",
                label_to_val=tag_options,
                selected_labels=[t.name for t in gwr.exclude_tags],
            ),
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
                selected_labels=[
                    {
                        ProductivityLevel.VERY_PRODUCTIVE.value: "Very productive",
                        ProductivityLevel.PRODUCTIVE.value: "Productive",
                        ProductivityLevel.NEUTRAL.value: "Neutral",
                        ProductivityLevel.DISTRACTING.value: "Distracting",
                        ProductivityLevel.VERY_DISTRACTING.value: "Very distracting",
                    }[pl]
                    for pl in prod_levels
                ],
            ),
            div(class_="space-y-2")[
                div(class_="flex items-center justify-between")[
                    label(class_="label")["Days of week"],
                ],
                div(class_="flex flex-wrap gap-4")[
                    *[
                        label(class_="inline-flex items-center gap-2")[
                            htpy_input(
                                type="checkbox",
                                name="days[]",
                                value=val,
                                checked=(val in days_selected),
                            ),
                            span[text],
                        ]
                        for text, val in [
                            ("Mon", "monday"),
                            ("Tue", "tuesday"),
                            ("Wed", "wednesday"),
                            ("Thu", "thursday"),
                            ("Fri", "friday"),
                            ("Sat", "saturday"),
                            ("Sun", "sunday"),
                        ]
                    ]
                ],
            ],
            div(
                class_="space-y-2",
                x_data=(
                    "{ add() { let t = document.getElementById('edit-time-range-template'); "
                    "let c = t.content.cloneNode(true); document.getElementById('edit-time-range-list').appendChild(c); } }"
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
                *[
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
                            default_start=pair[0],
                            default_end=pair[1],
                        ),
                        create_button(
                            text="",
                            variant="secondary",
                            icon="plus",
                            attrs={
                                "type": "button",
                                "@click": "$el.parentElement.remove()",
                            },
                        ),
                    ]
                    for pair in time_pairs
                ],
                div(id="edit-time-range-list", class_="space-y-2")[""],
                time_template,
            ],
        ],
    ]

    post_path = f"/s/goals/{goal_id}/edit/{metric_slug(goal.metric)}"
    the_form = form(
        element_id="edit-goal-form",
        method="POST",
        **{
            "hx-post": post_path,
            "hx-target": "#content",
            "hx-swap": "outerHTML",
        },
    )[
        header,
        context_card,
        form_body,
        div(class_="card p-4 flex-row justify-around items-center mt-4")[
            create_button(
                text="Cancel",
                variant="secondary",
                attrs={
                    "hx-get": "/s/goals",
                    "hx-target": "#content",
                    "hx-swap": "outerHTML",
                    "type": "button",
                },
            ),
            create_button(
                text="Save Changes", variant="primary", attrs={"type": "submit"}
            ),
        ],
    ]

    return create_standard_content(user_settings=user_settings, content=[the_form])
