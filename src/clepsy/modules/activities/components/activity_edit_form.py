from typing import List
from zoneinfo import ZoneInfo

from htpy import Element, div, form, input as html_input, span

from clepsy.entities import (
    ActivityEvent,
    DBActivityEvent,
    DBTag,
    ProductivityLevel,
)
from clepsy.frontend.components import (
    create_multiselect,
    create_single_select,
    create_text_area,
    create_text_input,
)

from .event_editor import (
    create_event_editor,
)


def create_activity_edit_form(
    *,
    activity_id: int,
    name: str,
    description: str,
    productivity_level: ProductivityLevel,
    events: List[DBActivityEvent | ActivityEvent],
    selected_tags: List[DBTag],
    all_tags: List[DBTag],
    user_timezone_str: str,
) -> Element:
    """
    Creates an editable form fragment for an activity, intended for a modal body.

    Args:
        activity_spec: The activity data including its tags.
        all_tags: A list of all available tags for the multiselect options.
        user_timezone_str: The user's timezone as a string.

    Returns:
        An htpy Element representing the form.
    """
    user_tz = ZoneInfo(user_timezone_str)

    event_times_localized = []
    event_types = []
    event_ids = []
    for event in events:
        event_time_localized = event.event_time.astimezone(user_tz).replace(tzinfo=None)
        event_times_localized.append(event_time_localized)
        event_types.append(event.event_type)
        event_ids.append(
            event.id if isinstance(event, DBActivityEvent) else "NEW_EVENT"
        )

    productivity_options = {
        level.name.replace("_", " ").title(): level.value for level in ProductivityLevel
    }

    tag_options = {tag.name: tag.id for tag in all_tags}
    selected_tag_labels = [tag.name for tag in selected_tags]

    return form(
        id=f"edit-form-{activity_id}",
        hx_post=f"/s/update-activity/{activity_id}",
        hx_target=f"#edit-modal-{activity_id}",
        hx_swap="outerHTML",
        class_="w-full flex flex-col space-y-4 form",  # Removed items-center
        x_data=True,
    )[
        # Hidden input for activity ID
        html_input(type="hidden", name="activity_id", value=str(activity_id)),
        # Wrapper div to center the top form fields
        div(class_="flex flex-col items-center space-y-4")[
            # Activity Name
            create_text_input(
                element_id=f"activity_name_{activity_id}",
                name="activity_name",
                title="Activity Name",
                value=name,
                required=True,
                extra_classes="w-full",
                attrs={"type": "text"},
            ),
            create_text_area(
                element_id=f"activity_description_{activity_id}",
                name="activity_description",
                title="Description",
                value=description,
                extra_classes="w-full",
                attrs={"type": "text"},
            ),
            create_single_select(
                element_id=f"productivity_level_{activity_id}",
                name="productivity_level",
                title="Productivity Level",
                options=productivity_options,
                selected_val=productivity_level.value,
            ),
            create_multiselect(
                element_id=f"tags_{activity_id}",
                name="tag_ids",  # Ensure name is provided for form submission
                title="Tags",
                label_to_val={key: str(val) for key, val in tag_options.items()},
                selected_labels=selected_tag_labels,
            ),
        ],  # Close the wrapper div for top fields
        div(class_="w-full border-t border-outline pt-4 mt-4 overflow-auto")[
            span(class_="text-sm font-medium text-on-surface-strong mb-2 block")[
                "Activity Events"
            ],
            create_event_editor(
                event_times=event_times_localized,
                event_types=event_types,
                event_ids=event_ids,
            ),  # Pass DBActivityEvent list
        ],
        # Removed hidden input for tag_ids
    ]
