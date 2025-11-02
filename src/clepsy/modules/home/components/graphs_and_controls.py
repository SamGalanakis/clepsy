from datetime import datetime, timezone
import json
from zoneinfo import ZoneInfo

import aiosqlite
from htpy import Element, div, form

# from datetime import timedelta  # no longer used here
from clepsy import utils
from clepsy.db.queries import (
    select_last_aggregation,
    select_specs_with_tags_and_sessions_in_time_range,
    select_tags,
    select_user_settings,
)
from clepsy.entities import DBTag, ViewMode, get_view_mode_label
from clepsy.frontend.components import (
    create_button,
    create_generic_modal,
    create_multiselect,
    create_single_select,
    create_time_nav_group,
)

from .unified_diagram import create_unified_diagram_container


def create_controls(
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
    if -1 in selected_tag_ids:  # Handle "No Tags" selection explicitly if needed
        selected_labels.append("No Tags")

    tag_selector = create_multiselect(
        element_id="tag-selector",
        name="tag_ids",
        title=None,
        label_to_val=label_to_val,
        selected_labels=selected_labels,
        # Control width solely via outer wrapper (responsive + allows shrink)
        outer_div_attrs_update={
            "class": "flex min-w-0 w-full sm:w-auto flex-col gap-2 max-w-[18rem] md:max-w-[22rem] lg:max-w-[26rem]",
        },
        x_model="selected_tag_ids",
    )

    # Time navigation (reusable): current range + chevrons
    time_nav_group = create_time_nav_group()

    add_activity_button = create_button(
        text="Add Activity",
        variant="primary",
        attrs={
            "hx-get": "/s/activities/add-activity-modal",
            "hx-target": "#add-activity-modal-content",
            "hx-swap": "innerHTML",
            "onclick": "document.getElementById('add-activity-modal').showModal()",
        },
    )

    # Main unified control bar with better visual hierarchy
    controls_container = div(
        class_="bg-card border border-border rounded-lg shadow-sm mb-6 overflow-y-visible"
    )[
        # Responsive row that wraps cleanly with consistent spacing
        div(
            class_="flex flex-wrap items-center gap-x-3 gap-y-2 sm:gap-x-4 sm:gap-y-3 lg:gap-x-6 p-4 w-full max-w-screen-xl mx-auto justify-center"
        )[
            # Left section: Filters
            form(
                # Compact controls that wrap nicely; center when alone on a row
                class_="order-1 flex flex-wrap items-center justify-center gap-2 sm:gap-3 min-w-0",
                **{"@submit.prevent": ""},  # Prevent form submission
            )[
                tag_selector,
                view_mode_selector,
            ],
            # Right cluster: Date navigation + Add button side-by-side
            div(
                class_="order-2 w-auto flex items-center justify-center gap-2 sm:gap-3"
            )[time_nav_group, add_activity_button],
        ],
    ]

    return controls_container


async def create_graphs_and_controls(
    conn: aiosqlite.Connection,
    reference_date_user_tz: datetime,
    current_time_user_tz: datetime,  # Add current time parameter
    view_mode: ViewMode,
    offset: int,
    selected_tag_ids: list[int],
):
    # Get user settings and timezone
    user_settings = await select_user_settings(conn)
    if user_settings is None:
        raise ValueError("User settings not found in the database")
    user_tz = ZoneInfo(user_settings.timezone)

    if not reference_date_user_tz.tzinfo == user_tz:
        raise ValueError("Reference date timezone does not match user timezone")

    start_time_user_tz, end_time_user_tz = utils.calculate_date_based_on_view_mode(
        reference_date=reference_date_user_tz,
        view_mode=view_mode,
        offset=offset,
    )
    start_time_utc = start_time_user_tz.astimezone(timezone.utc)
    end_time_utc = end_time_user_tz.astimezone(timezone.utc)

    db_activity_specs_with_tags_and_sessions = (
        await select_specs_with_tags_and_sessions_in_time_range(
            conn=conn,
            start=start_time_utc,
            end=end_time_utc,
        )
    )

    db_activity_specs_with_tags_and_sessions_user_tz = [
        x.to_tz(user_tz) for x in db_activity_specs_with_tags_and_sessions
    ]

    last_aggregation = await select_last_aggregation(conn=conn)
    if last_aggregation:
        last_aggregation_end_time_utc = last_aggregation.end_time
        last_aggregation_end_time_user_tz = last_aggregation_end_time_utc.astimezone(
            user_tz
        )
    else:
        last_aggregation_end_time_user_tz = None
    all_tags = await select_tags(conn)

    controls = create_controls(
        all_tags=all_tags,
        selected_tag_ids=selected_tag_ids,
        selected_view_mode=view_mode,
    )

    unified_diagram = create_unified_diagram_container(
        activity_specs=db_activity_specs_with_tags_and_sessions_user_tz,
        start_time_user_tz=start_time_user_tz,
        end_time_user_tz=end_time_user_tz,
        last_aggregation_end_time_user_tz=last_aggregation_end_time_user_tz,
        current_time_user_tz=current_time_user_tz,
    )

    x_data_str = """{
            reference_date: '[[$reference_date]]',
            view_mode: '[[$view_mode]]',
            selected_tag_ids: [[$selected_tag_ids_json]],
            offset: [[$offset]],
            dispatch_events() {
                console.log('Dispatching events for unified diagram');
                this.$dispatch('update_unified_diagram')
            },
        }"""

    selected_tag_ids_json = json.dumps(selected_tag_ids)
    x_data_str = utils.substitute_template(
        x_data_str,
        {
            "reference_date": utils.datetime_to_iso_8601(reference_date_user_tz),
            "view_mode": view_mode.value,
            "offset": offset,
            "selected_tag_ids_json": selected_tag_ids_json,
        },
    )

    # Convert the x_init to a single line to avoid HTML escaping issues with multiline strings
    x_init_str = """
$watch(() => view_mode, (newValue, oldValue) => {
    console.log('View mode changed from', oldValue, 'to', newValue);
    if (offset != 0) {
        offset = 0;
    } else {
        dispatch_events();
        $dispatch('date_range_changed');
    }
});
$watch(() => selected_tag_ids, () => {
    console.log('Selected tags changed:', selected_tag_ids);
    dispatch_events();
});
$watch(() => offset, () => {
    console.log('Offset changed:', offset);
    $dispatch('date_range_changed');
    dispatch_events();
});

""".strip()

    activity_edit_modal = create_generic_modal(
        modal_id="edit-activity-modal",
        content_id="edit-activity-modal-content",
        extra_classes="w-[92vw] sm:max-w-[480px] md:max-w-[560px] lg:max-w-[640px] xl:max-w-[720px]",
    )

    return div(
        id="graphs-and-controls",
        x_data=x_data_str,
        x_init=x_init_str,
    )[
        div(
            id="graphs-and-controls-container", class_="card overflow-y-auto scrollbar"
        )[
            div(id="graphs-and-controls-inner-container")[
                controls,
                unified_diagram,
            ],
        ],
        # Place modal outside the scrollable card, like the add modal
        activity_edit_modal,
    ]
