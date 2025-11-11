from datetime import datetime

from htpy import Element, div, input as html_input, template

from clepsy.entities import (
    ActivityEventType,
)  # Need DBActivityEvent for ID
from clepsy.frontend.components import (
    create_button,
    create_datetimepicker,
    create_tooltip,
)
from clepsy.frontend.components.icons import get_icon_svg


def create_event_row(
    event_time: datetime | None,
    event_type: ActivityEventType,
    index: int | str,
    event_id: int | str,
) -> Element:
    """Creates a single row for an event, either prefilled or as a template."""

    if event_time:
        assert (
            event_time.tzinfo is None
        ), "Event time should be timezone-naive and assumed to be in user's local time"

    drag_handle = div(**{"x-sort:handle": True})[get_icon_svg("drag_handle")]

    return div(
        class_="flex gap-2 items-center p-1 rounded event-row",
        id=f"event-row-{index}",
        **{"x-sort:item": True},
    )[
        html_input(name="event_id[]", type="hidden", value=event_id),
        drag_handle,
        create_datetimepicker(
            element_id=f"event_time_{index}",  # Use index/key for unique ID
            name="event_time[]",  # Use array notation
            title="",  # No visible title
            initial_value=event_time,
            attrs={},  # No Alpine needed
            mode="single",
            enable_time=True,
            placeholder="Select event time",
            # append_to_closest_selector="dialog",
        ),
        div(x_data=f'{{ "event_type": "{event_type}" }}')[
            create_button(
                text="",
                variant="secondary",
                icon=None,
                attrs={
                    "id": f"event_type_{index}",
                    "type": "button",
                    "x-text": "event_type",
                    "x-on:click": "if (event_type === 'open') { event_type = 'close'; } else { event_type = 'open'; }",
                },
            ),
            html_input(
                type="hidden",
                name="event_type[]",
                value=event_type.value,
            ),
        ],
        create_button(
            variant="secondary",
            icon="delete",
            text="",
            attrs={
                "@click": "$el.closest('.event-row').remove()",
            },
        ),
    ]


def create_event_editor(
    event_times: list[datetime],
    event_types: list[ActivityEventType],
    event_ids: list[int | str],
) -> Element:  # Expect DB events now
    """
    Creates an editable list of activity events generated on the server-side.
    Uses standard form submission with array notation.

    Args:
        events: The initial list of DBActivityEvent objects.

    Returns:
        An htpy Element containing the event editor UI.
    """

    event_tuples = list(zip(event_times, event_types, event_ids))
    event_tuples.sort(key=lambda x: x[0])  # Sort by time, None last

    event_rows = []
    for index, (event_time, event_type, event_id) in enumerate(event_tuples):
        event_row = create_event_row(
            event_time=event_time, event_type=event_type, index=index, event_id=event_id
        )

        event_rows.append(event_row)

    template_row = create_event_row(
        event_time=None,
        event_type=ActivityEventType.CLOSE,
        event_id="NEW_EVENT",
        index="new",
    )  # Template for new events
    template_row = template(id="event-row-template")[template_row]

    tooltip = create_tooltip(
        button_text="i",
        side="top",
        tooltip_text="""The progression of activities is tracked by a sequence of events.
        Each event is a timestamped record of an activity and is of a specific type.

        Event types:
        - Open: Marks the beggining or resumption of an activity.
        - Close: Marks the completion or temporary pause of an activity.
        """,
    )

    return div(
        class_="event-editor-container space-y-3 border p-3 rounded border-outline overflow-y-auto scrollbar card",
        x_data="""{

        "addNewEventRow"() {
        let temp = document.getElementById('event-row-template');
        let clone = temp.content.cloneNode(true);
        document.getElementById('event-list-container').appendChild(clone);
        }
        }""",
    )[
        # Wrap tooltip in a div and push it to the right
        div(class_="flex justify-end !overflow-visible")[tooltip],
        template_row,
        # Container for event rows, target for adding new rows
        div(
            id="event-list-container",
            class_="w-full space-y-2 max-h-60 pr-2 overflow-y-auto scrollbar",  # Added w-full
            x_sort=True,
        )[
            *event_rows  # Unpack the generated rows
        ],
        # Add Event button using HTMX to fetch a new row
        div(class_="flex justify-center pt-2 ")[
            create_button(
                text=None,
                variant="secondary",
                icon="plus",
                attrs={
                    "@click": "addNewEventRow()",
                    "aria-label": "Add new event",
                    "type": "button",
                },
            )
        ],
    ]
