from datetime import datetime
from zoneinfo import ZoneInfo

import aiosqlite

# Need template for the new modal pattern
from htpy import Element

from clepsy import utils

# Import button specifically if needed, or rely on __init__
from clepsy.db.queries import (
    select_tags,
)
from clepsy.entities import (
    UserSettings,  # Re-add DBActivitySpecWithTags
    ViewMode,  # Re-add DBActivitySpecWithTags
)

# Import necessary components and queries
from clepsy.frontend.components import create_standard_content

# Import home page specific components using absolute path
from .components import (
    create_graphs_and_controls,
)


# Removed modal helper functions as they are moved


async def create_home_page(
    conn: aiosqlite.Connection, user_settings: UserSettings
) -> Element:
    # Get user settings to determine the timezone (needed for formatting only now)
    user_timezone = ZoneInfo(user_settings.timezone)
    current_user_time = datetime.now(user_timezone)

    assert (
        current_user_time.tzinfo == user_timezone
    ), "Start time is not in the correct timezone"

    # Fetch all tags for the filter UI
    all_tags = await select_tags(conn)

    # Include required JS files (D3 is loaded in base_page)

    notag_value = -1
    selected_tag_ids: list[int] = [tag.id for tag in all_tags] + [notag_value]
    assert all(
        isinstance(tag_id, int) for tag_id in selected_tag_ids
    ), "Tag IDs must be integers"

    start_of_day_user_tz = utils.datetime_to_start_of_day(current_user_time)

    graphs_and_controls = await create_graphs_and_controls(
        conn=conn,
        reference_date_user_tz=start_of_day_user_tz,
        current_time_user_tz=current_user_time,  # Pass current time
        view_mode=ViewMode.DAILY,
        offset=0,
        selected_tag_ids=selected_tag_ids,
    )

    return create_standard_content(
        user_settings=user_settings,
        content=graphs_and_controls,
        inner_classes="mx-auto w-full max-w-screen-2xl min-w-[360px] px-4 sm:px-6 lg:px-8",
    )
