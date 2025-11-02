import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from htpy import Element, div, p
from loguru import logger
from pydantic import BaseModel

from clepsy.db.db import get_db_connection
from clepsy.db.queries import bulk_upsert_tags, select_tags
from clepsy.entities import DBTag, Tag
from clepsy.frontend.components import create_button
from clepsy.modules.user_settings.page import create_tags_page


router = APIRouter(prefix="/tags")


class TagForm(BaseModel):
    id: str
    name: str
    description: str | None = None


class TagsUpdateRequest(BaseModel):
    tags: list[TagForm]


def create_error_message(message: str) -> Element:
    return div(
        class_="p-4 mb-4 text-sm text-destructive-foreground bg-destructive rounded-lg flex justify-between items-center",
        role="alert",
    )[
        p[message],
        create_button(
            text=None,
            variant="destructive",
            size="sm",
            icon="plus",
            attrs={
                "type": "button",
                "@click": "$el.closest('[role=\\'alert\\']').remove()",
                "aria-label": "Close",
            },
        ),
    ]


async def get_tags_update_request(request: Request) -> TagsUpdateRequest:
    # Get the form data
    form_data = await request.form()

    # Log the raw form data for debugging
    logger.debug(f"Raw form data: {form_data}")

    # Get the tags_json from the form
    tags_json = form_data.get("tags_data", "{}")

    # Log the tags JSON for debugging
    logger.debug(f"Tags JSON: {tags_json}")

    # If tags_json is empty or just '{}', return an empty TagsUpdateRequest
    if not tags_json or tags_json == "{}":
        logger.warning("Received empty tags data!")
        return TagsUpdateRequest(tags=[])
    assert isinstance(tags_json, str), "Tags data must be a string"
    # Parse the JSON into a Python dictionary
    tags_data = json.loads(tags_json)
    tags_data = [TagForm(**tag) for tag in tags_data]

    logger.debug(f"Parsed tags data: {tags_data}")
    # Validate and return the TagsUpdateRequest
    return TagsUpdateRequest(tags=tags_data)


@router.post("/update-tags")
async def update_tags(
    tags_request: TagsUpdateRequest = Depends(get_tags_update_request),
) -> HTMLResponse:
    # Process the update request
    logger.debug(f"Processing update for {len(tags_request.tags)} tags")

    async with get_db_connection(include_uuid_func=True) as conn:
        # Get current tag IDs in database to determine which to delete
        existing_tags = await select_tags(conn)
        existing_ids = {tag.id for tag in existing_tags}

        # Enforce unique tag names at the router level (case-insensitive),
        # considering only submitted/active tags. Soft-deleted tags are not included.
        normalized_names = [
            tag.name.strip().lower()
            for tag in tags_request.tags
            if tag.name and tag.name.strip()
        ]
        if len(normalized_names) != len(set(normalized_names)):
            logger.warning(
                "Duplicate tag names detected in submission (app-level enforcement)"
            )
            response = HTMLResponse(
                content=create_error_message("Error: Tag names must be unique."),
            )
            response.headers["HX-Retarget"] = "#tags-error-container"
            response.headers["HX-Reswap"] = "innerHTML"
            return response

        # Split tags into new and existing based on ID
        tags_to_update = []
        tags_to_insert = []
        form_ids = set()

        for tag_form in tags_request.tags:
            # Ensure name is not empty
            if not tag_form.name or not tag_form.name.strip():
                logger.warning(f"Skipping tag with empty name: {tag_form}")
                continue  # Skip tags with empty names

            if tag_form.id.startswith("new"):
                # This is a new tag - handle None description
                tag = Tag(name=tag_form.name, description=tag_form.description or "")
                tags_to_insert.append(tag)
            else:
                # This is an existing tag - handle None description
                try:
                    tag_id = int(tag_form.id)
                    form_ids.add(tag_id)
                    tag = DBTag(
                        id=tag_id,
                        name=tag_form.name,
                        description=tag_form.description or "",
                    )
                    tags_to_update.append(tag)
                except ValueError:
                    logger.exception(
                        "Invalid tag ID received while updating tags: {}",
                        tag_form.id,
                    )
                    response = HTMLResponse(
                        content=create_error_message(
                            f"Error: Invalid tag ID {tag_form.id}"
                        ),
                        status_code=400,
                    )
                    response.headers["HX-Retarget"] = "#tags-error-container"
                    response.headers["HX-Reswap"] = "innerHTML"
                    return response

        # Find IDs to delete
        ids_to_delete = list(existing_ids - form_ids)

        try:
            # Perform the bulk operation
            await bulk_upsert_tags(conn, tags_to_update, tags_to_insert, ids_to_delete)

            # Explicitly commit the transaction
            await conn.commit()
            logger.debug("Transaction committed - updated tags in database")

            # Fetch updated tags list
            tags_page = await create_tags_page(conn)

            # Create response with success toast
            response = HTMLResponse(content=str(tags_page))

            # Determine what operations were performed for the success message
            operations = []
            if tags_to_insert:
                operations.append(f"{len(tags_to_insert)} added")
            if tags_to_update:
                operations.append(f"{len(tags_to_update)} updated")
            if ids_to_delete:
                operations.append(f"{len(ids_to_delete)} deleted")

            operation_text = ", ".join(operations) if operations else "no changes made"

            response.headers["HX-Trigger"] = json.dumps(
                {
                    "basecoat:toast": {
                        "config": {
                            "category": "success",
                            "title": "Tags Updated",
                            "description": f"Tags successfully updated ({operation_text}).",
                        }
                    }
                }
            )
            return response

        except Exception as exc:
            await conn.rollback()
            logger.exception("Error updating tags: {error}", error=exc)
            response = HTMLResponse(
                content=create_error_message(
                    f"An unexpected error occurred: {str(exc)}"
                ),
                status_code=500,
            )
            response.headers["HX-Retarget"] = "#tags-error-container"
            response.headers["HX-Reswap"] = "innerHTML"
            return response
