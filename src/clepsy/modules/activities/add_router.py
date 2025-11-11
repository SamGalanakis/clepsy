import asyncio
from datetime import datetime, timezone
import json
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Form
from fastapi.responses import HTMLResponse, JSONResponse
from htpy import Element, div, p  # Import Element
from loguru import logger

# Correct imports
from clepsy.db.db import get_db_connection
from clepsy.db.deps import get_user_settings
from clepsy.db.queries import (
    insert_activities,
    insert_activity_events,
    insert_tag_mappings,
    select_tags,
    select_user_settings,
)
from clepsy.entities import (
    Activity,
    ActivityEvent,
    ActivityEventInsert,
    ActivityEventType,
    CheckWithError,
    DBTag,
    ProductivityLevel,
    Source,
    TagMapping,
    UserSettings,
)

# Import components needed for wrapping the form and buttons
from clepsy.frontend.components import (
    create_button,
    default_python_datetime_format,
)
from clepsy.modules.home.components import create_activity_edit_form

# Import auth dependency
# Import the check function
from clepsy.utils import check_activity_events


router = APIRouter()


async def render_add_activity_modal_content(
    all_tags: list[DBTag],
    user_timezone_str: str,  # Added user_timezone_str
    activity_name: str = "",
    activity_description: str = "",
    productivity_level: ProductivityLevel = ProductivityLevel.NEUTRAL,
    selected_tag_ids: set[int] | None = None,
    parsed_events: list[ActivityEvent] | None = None,
    error_message: str | None = None,
) -> Element:  # Corrected return type hint
    selected_tag_ids = selected_tag_ids or set()
    parsed_events = parsed_events or []
    selected_tags = [tag for tag in all_tags if tag.id in selected_tag_ids]

    form_html = create_activity_edit_form(
        activity_id=-1,
        name=activity_name,
        description=activity_description,
        productivity_level=productivity_level,
        events=parsed_events,
        selected_tags=selected_tags,
        all_tags=all_tags,
        user_timezone_str=user_timezone_str,
    )
    form_body = form_html

    modal_header = div(class_="flex justify-between items-center p-4 border-b")[
        p(class_="text-lg font-semibold text-on-surface")["Add Activity"],
        create_button(
            text=None,
            variant="secondary",
            icon="x",
            attrs={
                "onclick": "document.getElementById('add-activity-modal').close();",
                "aria-label": "Close modal",
                "type": "button",
            },
        ),
    ]

    footer_content = div(class_="flex justify-end gap-2")[
        create_button(
            variant="secondary",
            text="Cancel",
            attrs={
                "onclick": "document.getElementById('add-activity-modal').close();",
                "type": "button",
            },
        ),
        create_button(
            variant="primary",
            text="Submit",
            attrs={"form": "add-form", "type": "submit"},
        ),
    ]

    error_div = div()
    if error_message:
        error_div = div(
            class_="p-2 mb-2 text-sm text-red-700 bg-red-100 border border-red-400 rounded"
        )[p(class_="font-medium")["Error:"], p[error_message]]

    actual_content_wrapper = div(class_="flex flex-col gap-4 p-4")[
        error_div,
        form_body(
            hx_post="/s/activities/add-activity",
            hx_target="#add-activity-modal-content",  # Target the content div
            id="add-form",
        ),
        footer_content,
    ]

    # This is the full content that will be rendered inside the dialog
    modal_content_panel = div(
        class_="bg-surface rounded-lg shadow-lg max-h-[90dvh] overflow-y-auto overflow-x-hidden max-w-full",
    )[modal_header, actual_content_wrapper]

    return modal_content_panel


@router.get("/add-activity-modal", response_class=HTMLResponse)
async def get_add_activity_modal(
    user_settings: UserSettings = Depends(get_user_settings),
):
    async with get_db_connection(include_uuid_func=False) as conn:
        all_tags = await select_tags(conn)
        user_timezone_str = user_settings.timezone  # Get timezone string

        user_tz = ZoneInfo(user_settings.timezone)
        start_now_event_time = datetime.now(user_tz)
        event = ActivityEvent(
            event_type=ActivityEventType.OPEN,
            event_time=start_now_event_time,
        )

        modal_content = await render_add_activity_modal_content(
            all_tags,
            user_timezone_str=user_timezone_str,  # Pass user_timezone_str
            parsed_events=[event],
        )
    return HTMLResponse(content=modal_content)


@router.post("/add-activity", response_class=HTMLResponse)
async def add_activity(
    activity_name: str = Form(...),
    activity_description: str = Form(...),
    productivity_level: ProductivityLevel = Form(...),
    tag_ids: list[str] = Form(default=[], alias="tag_ids"),
    event_time_list: list[str] = Form(default=[], alias="event_time[]"),
    event_type_list: list[ActivityEventType] = Form(default=[], alias="event_type[]"),
):
    tag_ids_int_set = set([int(x) for x in tag_ids])
    entry_time = datetime.now(timezone.utc)

    parsed_events: list[ActivityEvent] = []
    user_settings = None
    user_tz = None
    all_tags_for_render: list[DBTag] = []

    try:
        async with get_db_connection(
            commit_on_exit=True, start_transaction=True
        ) as conn:
            user_settings = await select_user_settings(conn)
            all_tags_for_render = await select_tags(conn)

            if not user_settings:
                logger.error("User settings not found during event parsing.")
                # Return error modal with toast notification
                modal_content_error = await render_add_activity_modal_content(
                    all_tags=all_tags_for_render,
                    user_timezone_str="UTC",  # Fallback timezone
                    error_message="Could not load user settings",
                    activity_name=activity_name,
                    activity_description=activity_description,
                    productivity_level=productivity_level,
                    selected_tag_ids=tag_ids_int_set,
                    parsed_events=parsed_events,
                )
                response = HTMLResponse(content=modal_content_error)
                response.headers["HX-Trigger"] = json.dumps(
                    {
                        "basecoat:toast": {
                            "config": {
                                "category": "error",
                                "title": "Configuration Error",
                                "description": "Could not load user settings. Please try again.",
                            }
                        }
                    }
                )
                return response

            user_tz = ZoneInfo(user_settings.timezone)

            # --- Event Parsing ---
            try:
                for event_time_str, event_type in zip(event_time_list, event_type_list):
                    event_time_naive = datetime.strptime(
                        event_time_str, default_python_datetime_format
                    )
                    event_time_user_tz = event_time_naive.replace(tzinfo=user_tz)
                    event_time_utc = event_time_user_tz.astimezone(timezone.utc)

                    parsed_events.append(
                        ActivityEvent(event_type=event_type, event_time=event_time_utc)
                    )
            except ValueError as exc:
                logger.exception(
                    "Date parsing error while adding activity '{name}': {error}",
                    name=activity_name,
                    error=exc,
                )
                modal_content_error = await render_add_activity_modal_content(
                    all_tags=all_tags_for_render,
                    user_timezone_str=user_settings.timezone,
                    error_message=f"Invalid date format: {str(exc)}",
                    activity_name=activity_name,
                    activity_description=activity_description,
                    productivity_level=productivity_level,
                    selected_tag_ids=tag_ids_int_set,
                    parsed_events=parsed_events,
                )
                response = HTMLResponse(content=modal_content_error)
                response.headers["HX-Trigger"] = json.dumps(
                    {
                        "basecoat:toast": {
                            "config": {
                                "category": "warning",
                                "title": "Invalid Date Format",
                                "description": "Please check the date and time format and try again.",
                            }
                        }
                    }
                )
                return response

            # --- Event Validation ---
            validation_result: CheckWithError = check_activity_events(
                parsed_events, activity_completed=True
            )

            if not validation_result.result:
                modal_content_error = await render_add_activity_modal_content(
                    all_tags=all_tags_for_render,
                    user_timezone_str=user_settings.timezone,
                    error_message=validation_result.error,
                    activity_name=activity_name,
                    activity_description=activity_description,
                    productivity_level=productivity_level,
                    selected_tag_ids=tag_ids_int_set,
                    parsed_events=parsed_events,
                )
                response = HTMLResponse(content=modal_content_error)
                response.headers["HX-Trigger"] = json.dumps(
                    {
                        "basecoat:toast": {
                            "config": {
                                "category": "warning",
                                "title": "Validation Error",
                                "description": validation_result.error
                                or "Please check your activity events and try again.",
                            }
                        }
                    }
                )
                return response

            activity = Activity(
                name=activity_name,
                description=activity_description,
                productivity_level=productivity_level,
                source=Source.MANUAL,
                last_manual_action_time=entry_time,
            )
            activity_id = (await insert_activities(conn, [activity]))[0]
            db_tag_mapping = [
                TagMapping(activity_id=activity_id, tag_id=int(tag_id))
                for tag_id in tag_ids
            ]
            db_events_to_insert = [
                ActivityEventInsert(
                    activity_id=activity_id,
                    event_time=parsed_event.event_time,
                    event_type=parsed_event.event_type,
                    aggregation_id=None,
                    last_manual_action_time=entry_time,
                )
                for parsed_event in parsed_events
            ]
            tag_mapping_insert_task = insert_tag_mappings(conn, db_tag_mapping)
            event_insert_task = insert_activity_events(conn, db_events_to_insert)
            await asyncio.gather(tag_mapping_insert_task, event_insert_task)

        response = JSONResponse(content="", status_code=200)
        response.headers["HX-Trigger"] = json.dumps(
            {
                "basecoat:toast": {
                    "config": {
                        "category": "success",
                        "title": "Activity Added",
                        "description": f"Successfully added '{activity_name}' to your activity log.",
                    }
                },
                "closemodal": {},
                "update_unified_diagram": {},
            }
        )
        response.headers["HX-Reswap"] = "none"

        return response

    except (ValueError, RuntimeError) as exc:
        logger.exception(
            "Unexpected error adding activity '{name}': {error}",
            name=activity_name,
            error=exc,
        )
        # Handle any unexpected errors
        error_message = div(class_="p-4 text-red-600")[
            p[
                "An unexpected error occurred while adding the activity. Please try again."
            ],
        ]
        response = HTMLResponse(content=error_message)
        response.headers["HX-Trigger"] = json.dumps(
            {
                "basecoat:toast": {
                    "config": {
                        "category": "error",
                        "title": "Unexpected Error",
                        "description": "Something went wrong while adding the activity. Please try again later.",
                    }
                }
            }
        )
        return response
