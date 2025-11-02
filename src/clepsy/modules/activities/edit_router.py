import asyncio
from datetime import datetime, timezone  # Import timezone
import json
from typing import Any, List, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse
from htpy import Element, div, p
from loguru import logger
from pydantic import BaseModel

from clepsy import utils
from clepsy.db.db import get_db_connection
from clepsy.db.deps import get_user_settings
from clepsy.db.queries import (
    delete_activity,  # Import delete_activity query
    delete_activity_events,
    delete_tag_mappings,
    insert_activity_events,
    insert_tag_mappings,
    select_activity_spec_with_tags,
    select_tags,
    select_user_settings,
    update_activity as update_activity_query,
    update_activity_event,
)

# Import ProductivityLevel enum and others
from clepsy.entities import (
    Activity,
    ActivityEvent,
    ActivityEventInsert,
    ActivityEventType,
    DBActivityEvent,
    DBActivitySpecWithTags,
    DBTag,
    ProductivityLevel,
    TagMapping,
    UserSettings,
)

# Import generic components
from clepsy.frontend.components import create_button, default_python_datetime_format

# Import page-specific components from their new location
from clepsy.modules.home.components import create_activity_edit_form


router = APIRouter()


async def render_edit_activity_modal_content(
    activity_spec: DBActivitySpecWithTags,
    all_tags: List[DBTag],
    user_timezone_str: str,
    error_message: str | None = None,
) -> Element:
    # Reuse form component with explicit args
    form_body = create_activity_edit_form(
        activity_id=activity_spec.activity.id,
        name=activity_spec.activity.name,
        description=activity_spec.activity.description,
        productivity_level=activity_spec.activity.productivity_level,
        events=activity_spec.events,  # type: ignore
        selected_tags=activity_spec.tags,
        all_tags=all_tags,
        user_timezone_str=user_timezone_str,
    )

    # Header (align with add modal: p-4 border-b, cross button closes dialog)
    modal_header = div(class_="flex justify-between items-center p-4 border-b")[
        p(class_="text-lg font-semibold text-on-surface")["Edit Activity"],
        create_button(
            text=None,
            variant="secondary",
            icon="x",
            attrs={
                "onclick": "document.getElementById('edit-activity-modal').close();",
                "aria-label": "Close modal",
            },
        ),
    ]

    # Error block (same styling as add modal)
    error_div = div()
    if error_message:
        error_div = div(
            class_="p-2 mb-2 text-sm text-red-700 bg-red-100 border border-red-400 rounded"
        )[p(class_="font-medium")["Error:"], p[error_message]]

    # Footer: Delete (left), then Cancel + Save (right) similar spacing semantics
    footer_content = div(class_="flex justify-between items-center")[
        create_button(
            variant="destructive",
            text="Delete",
            attrs={
                "hx-delete": f"/s/activities/delete-activity/{activity_spec.activity.id}",
                "hx-confirm": "Are you sure you want to delete this activity?",
                "hx-target": "this",
                "hx-swap": "none",
            },
        ),
        div(class_="flex justify-end gap-2")[
            create_button(
                variant="secondary",
                text="Cancel",
                attrs={
                    "hx-get": f"/s/edit-activity-modal?activity_id={activity_spec.activity.id}",
                    "hx-target": "#edit-activity-modal-content",
                },
            ),
            create_button(
                variant="primary",
                text="Save",
                attrs={
                    "form": f"edit-form-{activity_spec.activity.id}",
                    "type": "submit",
                },
            ),
        ],
    ]

    # Inner wrapper (same class naming as add modal for consistency)
    actual_content_wrapper = div(class_="flex flex-col gap-4 p-4")[
        error_div,
        form_body(
            hx_put=f"/s/activities/update-activity/{activity_spec.activity.id}",
            hx_target="#edit-activity-modal-content",
            id=f"edit-form-{activity_spec.activity.id}",
        ),
        footer_content,
    ]

    # Panel only (no backdrop); match add modal: cap height and enable internal scroll
    modal_content_panel = div(
        class_="bg-surface rounded-lg shadow-lg max-h-[90dvh] overflow-y-auto overflow-x-hidden max-w-full"
    )[
        modal_header,
        actual_content_wrapper,
    ]

    return modal_content_panel


@router.get("/edit-activity-modal", response_class=HTMLResponse)
async def get_activity_edit_modal(activity_id: int) -> HTMLResponse:
    """
    Fetches data for a specific activity (passed as query param) and returns an HTML fragment
    containing a modal with an editable form.
    """
    logger.debug(f"Fetching edit modal for activity_id: {activity_id}")
    async with get_db_connection(include_uuid_func=False) as conn:
        user_settings = await select_user_settings(conn)
        assert user_settings, "User settings not found"
        user_timezone_str = user_settings.timezone

        # Fetch the specific activity details including tags
        activity_spec = await select_activity_spec_with_tags(conn, activity_id)
        if not activity_spec:
            logger.error(f"Activity not found: {activity_id}")
            return HTMLResponse(
                content="<p>Error: Activity not found.</p>", status_code=404
            )

        # Fetch all available tags for the multiselect options
        all_tags = await select_tags(conn)

        # Render the complete modal content using the helper function
        modal_content = await render_edit_activity_modal_content(
            activity_spec=activity_spec,
            all_tags=all_tags,
            user_timezone_str=user_timezone_str,
        )

        # Return the container with the header and content wrapper
        return HTMLResponse(content=modal_content)


class ActivityUpdateForm(BaseModel):
    # Single value fields from the form
    activity_name: str = Form(...)
    activity_description: str = Form(...)
    productivity_level: ProductivityLevel = Form(...)

    tag_ids: str = Form(...)  # Input is string like "[1,5]"

    event_id: List[Optional[str]] = Form(..., alias="event_id[]")
    event_time: List[str] = Form(..., alias="event_time[]")
    event_type: List[str] = Form(..., alias="event_type[]")


def check_event_edited(
    old_event: ActivityEvent | DBActivityEvent,
    new_event: ActivityEvent | DBActivityEvent,
) -> bool:
    if old_event.event_type != new_event.event_type:
        return True

    if not utils.dates_equal_to_minute(old_event.event_time, new_event.event_time):
        return True

    return False


def check_activity_edit(
    old_activity: Activity,
    new_activity: Activity,
) -> dict[str, Any]:
    changes = {}

    if old_activity.name != new_activity.name:
        changes["name"] = new_activity.name

    if old_activity.description != new_activity.description:
        changes["description"] = new_activity.description

    if old_activity.productivity_level != new_activity.productivity_level:
        changes["productivity_level"] = new_activity.productivity_level

    return changes


@router.put("/update-activity/{activity_id}")
async def update_activity(
    activity_id: int,
    activity_name: str = Form(...),
    activity_description: str = Form(...),
    productivity_level: ProductivityLevel = Form(...),
    tag_ids: List[str] = Form(default=[], alias="tag_ids"),
    event_time_list: List[str] = Form(..., alias="event_time[]"),
    event_type_list: List[ActivityEventType] = Form(..., alias="event_type[]"),
    event_id_list: List[str] = Form(..., alias="event_id[]"),
    user_settings: UserSettings = Depends(get_user_settings),
) -> HTMLResponse:
    try:
        tasks = []
        new_tag_ids = set([int(x) for x in tag_ids])

        edit_time = datetime.now(tz=timezone.utc)

        logger.info(f"Updating activity {activity_id}")

        if len(event_type_list) != len(event_time_list):
            raise HTTPException(
                status_code=400,
                detail="Event time and type lists must be of the same length",
            )

        async with get_db_connection(start_transaction=True) as conn:
            user_timezone = ZoneInfo(user_settings.timezone)

            old_activity_spec = await select_activity_spec_with_tags(conn, activity_id)

            old_tag_ids = {tag.id for tag in old_activity_spec.tags}

            removed_tag_ids = old_tag_ids - new_tag_ids
            added_tag_ids = new_tag_ids - old_tag_ids

            if removed_tag_ids:
                delete_tag_mappings_task = delete_tag_mappings(
                    conn,
                    activity_id,
                    list(removed_tag_ids),  # type: ignore
                )

                tasks.append(delete_tag_mappings_task)

            if added_tag_ids:
                tag_mappings_to_insert = [
                    TagMapping(
                        activity_id=activity_id,
                        tag_id=tag_id,
                    )
                    for tag_id in added_tag_ids
                ]

                await insert_tag_mappings(conn, mappings=tag_mappings_to_insert)

            old_db_activity = old_activity_spec.activity

            old_activity = old_db_activity

            new_activity = Activity(
                name=activity_name,
                description=activity_description,
                productivity_level=productivity_level,
                source=old_activity.source,
                last_manual_action_time=edit_time,
            )

            edited_cols_to_new_val_dict = check_activity_edit(
                old_activity=old_activity,
                new_activity=new_activity,
            )

            if edited_cols_to_new_val_dict:
                # Update the activity in the database

                edited_cols_to_new_val_dict["last_manual_action_time"] = edit_time

                activity_update_task = update_activity_query(
                    conn,
                    activity_id=activity_id,
                    key_value_pairs=edited_cols_to_new_val_dict,
                )

                tasks.append(activity_update_task)

            existing_activity_events = old_activity_spec.events

            old_event_ids = {event.id for event in existing_activity_events}

            old_events_by_id = {event.id: event for event in existing_activity_events}

            new_event_ids = set(
                [int(event_id) for event_id in event_id_list if event_id != "NEW_EVENT"]
            )

            event_ids_to_delete = old_event_ids - new_event_ids

            events_to_insert = []

            events_to_update = []

            for event_id, event_time_str, event_type in zip(
                event_id_list, event_time_list, event_type_list
            ):
                event_time_naive = datetime.strptime(
                    event_time_str, default_python_datetime_format
                )
                event_time_usertz = event_time_naive.replace(tzinfo=user_timezone)
                event_time_utc = event_time_usertz.astimezone(timezone.utc)

                if not event_id:
                    # New event, insert it
                    # Prepare insert-only event
                    events_to_insert.append(
                        ActivityEventInsert(
                            activity_id=activity_id,
                            event_time=event_time_utc,
                            event_type=event_type,
                            last_manual_action_time=edit_time,
                            aggregation_id=None,
                        )
                    )

                    continue

                corresponding_old_event = old_events_by_id[int(event_id)]

                new_activity_event = ActivityEvent(
                    event_time=event_time_utc,
                    event_type=event_type,
                )

                if not check_event_edited(
                    corresponding_old_event,
                    new_activity_event,
                ):
                    continue

                db_activity_event = DBActivityEvent(
                    activity_id=activity_id,
                    event_time=event_time_utc,
                    event_type=event_type,
                    id=int(event_id),
                    last_manual_action_time=edit_time,
                    aggregation_id=None,
                )
                events_to_update.append(db_activity_event)

            assert (
                None not in event_ids_to_delete
            ), "Event IDs to delete should not contain None"

            delete_task = delete_activity_events(
                conn,
                list(event_ids_to_delete),  # type: ignore
            )

            update_tasks = [
                update_activity_event(conn, event) for event in events_to_update
            ]

            insert_task = insert_activity_events(conn, events_to_insert)

            tasks.append(delete_task)
            tasks.extend(update_tasks)
            tasks.append(insert_task)

            await asyncio.gather(*tasks)

            updated_modal = await render_edit_activity_modal_content(
                activity_spec=await select_activity_spec_with_tags(conn, activity_id),
                all_tags=await select_tags(conn),
                user_timezone_str=user_settings.timezone,  # Pass user timezone string
            )

            response = HTMLResponse(content=updated_modal)

            # Trigger timeline refresh after successful save
            response.headers["HX-Trigger"] = json.dumps(
                {
                    "notify": {
                        "variant": "success",
                        "title": "Activity Updated",
                        "message": "Activity updated successfully!",
                    },
                    "update_unified_diagram": {},
                }
            )
            return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.delete("/delete-activity/{activity_id}", response_class=HTMLResponse)
async def handle_delete_activity(activity_id: int):
    try:
        logger.info(f"Attempting to delete activity {activity_id}")
        async with get_db_connection(start_transaction=True) as conn:
            await delete_activity(conn, activity_id)
            logger.info(f"Successfully deleted activity {activity_id}")

        response = HTMLResponse(content="", status_code=200)  # OK status
        response.headers["HX-Trigger"] = json.dumps(
            {
                "notify": {
                    "variant": "success",
                    "title": "Activity Deleted",
                    "message": "Activity has been successfully deleted.",
                },
                "update_unified_diagram": {},
                "closemodal": {},
            }
        )
        return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error") from e
