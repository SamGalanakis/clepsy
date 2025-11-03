from datetime import datetime, timezone
import json
from zoneinfo import ZoneInfo

from htpy import Element, div, form, script

from clepsy import utils
from clepsy.db.db import get_db_connection
from clepsy.db.queries import (
    select_last_aggregation,
    select_specs_with_tags_in_time_range,
    select_tags,
)
from clepsy.entities import DBTag, UserSettings, ViewMode, get_view_mode_label
from clepsy.frontend.components import (
    create_multiselect,
    create_single_select,
    create_standard_content,
    create_time_nav_group,
)
from clepsy.modules.insights.components.focus_sessions import (
    create_focus_sessions_section,
)
from clepsy.modules.insights.components.productivity_donut import (
    create_productivity_donut_body,
)
from clepsy.modules.insights.components.productivity_time_slice import (
    create_productivity_time_slice_body,
)
from clepsy.modules.insights.components.tag_transition_chord import (
    create_tag_transition_chord_container,
)
from clepsy.modules.insights.components.time_spent_per_tag import (
    create_time_spent_per_tag_container,
)


async def _build_controls(
    *,
    all_tags: list[DBTag],
    selected_tag_ids: list[int],
    selected_view_mode: ViewMode,
) -> Element:
    view_mode_selector = create_single_select(
        element_id="view-mode-selector",
        name="view_mode",
        x_model="view_mode",
        options={get_view_mode_label(mode): mode.value for mode in ViewMode},
        selected_val=selected_view_mode.value,
        title=None,
        outer_div_attrs_update={
            "class": "flex min-w-0 w-full sm:w-auto flex-col gap-2 max-w-[12rem]",
        },
    )

    label_to_val = {"No Tags": str(-1), **{tag.name: str(tag.id) for tag in all_tags}}
    selected_labels = [str(tag.name) for tag in all_tags if tag.id in selected_tag_ids]
    if -1 in selected_tag_ids:
        selected_labels.append("No Tags")

    tag_selector = create_multiselect(
        element_id="tag-selector",
        name="tag_ids",
        title=None,
        label_to_val=label_to_val,
        selected_labels=selected_labels,
        # Match home page control styling with main dashboard (responsive widths)
        outer_div_attrs_update={
            "class": "flex min-w-0 w-full sm:w-auto flex-col gap-2 max-w-[18rem] md:max-w-[22rem] lg:max-w-[26rem]",
        },
        x_model="selected_tag_ids",
    )

    time_nav_group = create_time_nav_group()

    # Updated layout to align with styling in graphs_and_controls (minus Add Activity button)
    return div(
        class_="bg-card border border-border rounded-lg shadow-sm mb-6 overflow-y-visible"
    )[
        div(
            class_="flex flex-wrap items-center gap-x-3 gap-y-2 sm:gap-x-4 sm:gap-y-3 lg:gap-x-6 p-4 w-full max-w-screen-xl mx-auto justify-center"
        )[
            form(
                class_="order-1 flex flex-wrap items-center justify-center gap-2 sm:gap-3 min-w-0",
                **{"@submit.prevent": ""},
            )[
                tag_selector,
                view_mode_selector,
            ],
            div(
                class_="order-2 w-auto flex items-center justify-center gap-2 sm:gap-3"
            )[time_nav_group,],
        ],
    ]


async def create_insights_page(user_settings: UserSettings) -> Element:
    user_tz = ZoneInfo(user_settings.timezone)
    current_time_user_tz = datetime.now(user_tz)
    start_of_day_user_tz = utils.datetime_to_start_of_day(current_time_user_tz)

    selected_view_mode = ViewMode.DAILY
    offset = 0

    # Fetch data needed for initial render
    async def get_initial(conn):
        all_tags = await select_tags(conn)
        selected_tag_ids = [tag.id for tag in all_tags] + [-1]
        start_user_tz, end_user_tz = utils.calculate_date_based_on_view_mode(
            reference_date=start_of_day_user_tz,
            view_mode=selected_view_mode,
            offset=offset,
        )
        specs, last_agg = (
            await select_specs_with_tags_in_time_range(
                conn,
                start=start_user_tz.astimezone(timezone.utc),
                end=end_user_tz.astimezone(timezone.utc),
            ),
            await select_last_aggregation(conn),
        )
        return all_tags, selected_tag_ids, start_user_tz, end_user_tz, specs, last_agg

    async with get_db_connection(include_uuid_func=False) as conn:
        (
            all_tags,
            selected_tag_ids,
            start_user_tz,
            end_user_tz,
            specs,
            last_agg,
        ) = await get_initial(conn)

    controls = await _build_controls(
        all_tags=all_tags,
        selected_tag_ids=selected_tag_ids,
        selected_view_mode=selected_view_mode,
    )

    # Graph containers (one per graph)
    time_spent_graph = create_time_spent_per_tag_container(
        activity_specs=[s for s in specs],
        start_time_user_tz=start_user_tz,
        end_time_user_tz=end_user_tz,
        last_aggregation_end_time_user_tz=(
            last_agg.end_time.astimezone(user_tz) if last_agg else None
        ),
        current_time_user_tz=current_time_user_tz,
    )

    productivity_graph_body = create_productivity_time_slice_body(
        activity_specs=[s for s in specs],
        start_time_user_tz=start_user_tz,
        end_time_user_tz=end_user_tz,
        last_aggregation_end_time_user_tz=(
            last_agg.end_time.astimezone(user_tz) if last_agg else None
        ),
        current_time_user_tz=current_time_user_tz,
        view_mode=selected_view_mode,
    )

    productivity_donut_body = create_productivity_donut_body(
        activity_specs=[s for s in specs],
        start_time_user_tz=start_user_tz,
        end_time_user_tz=end_user_tz,
        last_aggregation_end_time_user_tz=(
            last_agg.end_time.astimezone(user_tz) if last_agg else None
        ),
        current_time_user_tz=current_time_user_tz,
        view_mode=selected_view_mode,
    )

    productivity_graph_container = div(
        id="productivity-time-slice-wrapper",
        class_="insight-graph w-full min-w-0",
        **{
            "hx-get": "/s/insights/update-productivity-time-slice",
            "hx-trigger": "update_insights_diagrams from:body",
            "hx-target": "#productivity_time_slice_chart",
            "hx-swap": "outerHTML",
            "x-bind:hx-vals": (
                "JSON.stringify({reference_date: reference_date, view_mode: view_mode, offset: offset, selected_tag_ids: JSON.stringify(selected_tag_ids)})"
            ),
        },
    )[productivity_graph_body]

    productivity_donut_container = div(
        id="productivity-donut-wrapper",
        class_="insight-graph w-full min-w-0",
        **{
            "hx-get": "/s/insights/update-productivity-donut",
            "hx-trigger": "update_insights_diagrams from:body",
            "hx-target": "#productivity_donut_chart",
            "hx-swap": "outerHTML",
            "x-bind:hx-vals": (
                "JSON.stringify({reference_date: reference_date, view_mode: view_mode, offset: offset, selected_tag_ids: JSON.stringify(selected_tag_ids)})"
            ),
        },
    )[productivity_donut_body]

    # Alpine x-data and watchers to dispatch update_insights_diagrams
    x_data = utils.substitute_template(
        """{
            reference_date: '[[$reference_date]]',
            view_mode: '[[$view_mode]]',
            selected_tag_ids: [[$selected_tag_ids_json]],
            offset: [[$offset]],
            dispatch_events() {
                this.$dispatch('update_insights_diagrams');
            },
        }""",
        {
            "reference_date": utils.datetime_to_iso_8601(start_of_day_user_tz),
            "view_mode": selected_view_mode.value,
            "offset": offset,
            "selected_tag_ids_json": json.dumps(selected_tag_ids),
        },
    )

    x_init = (
        "$watch(() => view_mode, (n,o) => { if (offset!=0) { offset=0; } else { dispatch_events(); $dispatch('date_range_changed'); } });\n"
        + "$watch(() => selected_tag_ids, () => { dispatch_events(); });\n"
        + "$watch(() => offset, () => { $dispatch('date_range_changed'); dispatch_events(); });"
    )

    # Responsive graph layout (flex wrap)
    # Goals:
    # - Larger minimum width per graph (was ~380px). Increase to 500+ for better readability.
    # - Up to 3 per row within existing max container width (max-w-screen-2xl).
    # - Natural wrap on smaller screens to 1 or 2 columns.
    # Implementation notes:
    # We use flex-wrap with child sizing utilities applied via arbitrary selector syntax so we
    # don't have to modify each component's own classes. Child rules:
    #   * basis-[520px] & min-w-[520px] enforce larger minimum width (except on very narrow screens where they can overflow; w-full keeps them fluid).
    #   * grow allows them to stretch evenly when extra horizontal space < 3 columns.
    #   * On extremely narrow screens (<520px) the browser will still shrink below min-w via overflow rules; if this proves too rigid we can add responsive min-w breakpoints later.
    chord_graph_container = create_tag_transition_chord_container(
        [s for s in specs],
        start_time_user_tz=start_user_tz,
        end_time_user_tz=end_user_tz,
    )

    focus_sessions_section = create_focus_sessions_section(
        activity_specs=[s for s in specs],
        start_time_user_tz=start_user_tz,
        end_time_user_tz=end_user_tz,
        last_aggregation_end_time_user_tz=(
            last_agg.end_time.astimezone(user_tz) if last_agg else None
        ),
        current_time_user_tz=current_time_user_tz,
        view_mode=selected_view_mode,
    )

    graphs_grid = div(
        class_=(
            "flex flex-wrap justify-center gap-4 sm:gap-6 md:gap-7 xl:gap-8 w-full "
            "[&>.insight-graph]:w-full [&>.insight-graph]:grow "
            "[&>.insight-graph]:basis-full sm:[&>.insight-graph]:basis-[520px] "
            "sm:[&>.insight-graph]:min-w-[520px] [&>.insight-graph]:max-w-full"
        ),
    )[
        time_spent_graph,
        # Load productivity script once (after utils/chart utils from first graph)
        productivity_graph_container,
        productivity_donut_container,
        chord_graph_container,
        focus_sessions_section,
    ]

    # Flex layout auto-wraps: <520px = single column scroll (rare), ~520-1080px ≈ 1–2 columns, >= ~1580px fits 3 columns (given container max width).
    content = div(class_="card", x_data=x_data, x_init=x_init)[
        script(src="/static/custom_scripts/insights_productivity_time_slice.js"),
        script(src="/static/custom_scripts/insights_productivity_donut.js"),
        script(src="/static/custom_scripts/insights_focus_sessions.js"),
        div(class_="p-4 space-y-6")[
            controls,
            graphs_grid,
        ],
    ]

    return create_standard_content(
        user_settings=user_settings,
        content=content,
        inner_classes="mx-auto w-full max-w-screen-2xl px-4 sm:px-6 lg:px-8",
    )
