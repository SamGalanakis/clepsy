from datetime import datetime, timezone as dt_timezone

import aiosqlite
from htpy import (
    Element,
    Node,
    div,
    form,
    h2,
    input as htpy_input,
    label,
    p,
    table,
    tbody,
    td,
    th,
    thead,
    tr,
)
from loguru import logger

from clepsy.db.queries import select_sources, select_tags, select_user_settings
from clepsy.entities import DBDeviceSource, SourceStatus, UserSettings
from clepsy.frontend.components import (
    common_timezones_list,
    create_button,
    create_generic_modal,
    create_markdown_editor,
    create_single_select,
    create_standard_content,
    create_text_input,
)

# removed get_icon_svg import; test modals handled inside LLM component
from clepsy.modules.user_settings.llm.component import create_llm_editor
from clepsy.modules.user_settings.tags.component import create_tags_editor
from clepsy.utils import format_recent_or_ordinal


async def create_general_settings_page(
    user_settings: UserSettings,
    username_error: str | None = None,
    timezone_error: str | None = None,
    username_value: str | None = None,
    timezone_value: str | None = None,
) -> Element:
    form_inner_content = div(class_="card p-6 space-y-6")[
        h2(class_="text-lg font-semibold text-on-surface-strong mb-4")["General"],
        div(class_="grid gap-3 mt-4")[
            create_text_input(
                element_id="username",
                name="username",
                attrs={"type": "text"},
                value=(
                    (username_value or "")
                    if username_error is None and username_value is not None
                    else (username_value or "")
                ),
                placeholder="Enter a username",
                title="Username",
                valid_state=username_error is None,
            ),
            p(class_="text-destructive text-sm")[username_error]
            if username_error
            else None,
        ],
        div(class_="grid gap-3 mt-2")[
            create_single_select(
                element_id="timezone",
                include_search=True,
                name="timezone",
                placeholder_text="Select a timezone",
                title="Timezone",
                options={tz: tz for tz in common_timezones_list},
                selected_val=(None if timezone_error else timezone_value),
            ),
            p(class_="text-destructive text-sm")[timezone_error]
            if timezone_error
            else None,
        ],
    ]

    form_with_buttons = form(
        element_id="general-settings-form",
        method="POST",
        **{
            "hx-post": "/s/user-settings/general",
            "hx-target": "#content",
            "hx-swap": "outerHTML",
        },
    )[
        form_inner_content,
        div(class_="card p-4 flex-row justify-around items-center mt-4")[
            create_button(
                text="Cancel",
                variant="destructive",
                attrs={
                    "hx-get": "/s/user-settings/general",
                    "hx-target": "#content",
                    "hx-swap": "outerHTML",
                    "type": "button",
                },
            ),
            create_button(
                text="Save Changes",
                variant="primary",
                attrs={"type": "submit"},
                extra_classes="ml-3",
            ),
        ],
    ]

    return create_standard_content(
        user_settings=user_settings,
        content=[form_with_buttons],
    )


async def create_password_page(
    user_settings: UserSettings,
    current_password_error: str | None = None,
    new_password_error: str | None = None,
    confirm_password_error: str | None = None,
    new_password_value: str | None = None,
    confirm_password_value: str | None = None,
) -> Element:
    # user_settings is provided by caller

    form_inner_content = div(class_="card p-6 space-y-6")[
        h2(class_="text-lg font-semibold text-on-surface-strong mb-4")[
            "Change Password"
        ],
        div(class_="grid gap-3")[
            create_text_input(
                element_id="current-password",
                name="current_password",
                required=True,
                value="",  # Never preserve current password for security
                title="Current Password",
                attrs={"type": "password"},
                valid_state=current_password_error is None,
            ),
            p(class_="text-destructive text-sm")[current_password_error]
            if current_password_error
            else None,
        ],
        div(class_="grid gap-3")[
            create_text_input(
                element_id="new-password-change",
                name="new_password",
                required=True,
                value=new_password_value
                if new_password_error is None and new_password_value is not None
                else "",
                title="New Password",
                attrs={"type": "password"},
                valid_state=new_password_error is None,
            ),
            p(class_="text-destructive text-sm")[new_password_error]
            if new_password_error
            else None,
        ],
        div(class_="grid gap-3")[
            create_text_input(
                element_id="confirm-password",
                name="confirm_password",
                required=True,
                value=confirm_password_value
                if confirm_password_error is None and confirm_password_value is not None
                else "",
                title="Confirm New Password",
                attrs={"type": "password"},
                valid_state=confirm_password_error is None,
            ),
            p(class_="text-destructive text-sm")[confirm_password_error]
            if confirm_password_error
            else None,
        ],
    ]

    form_with_buttons = form(
        element_id="password-change-form",
        method="POST",
        **{
            "hx-post": "/s/change-password",
            "hx-target": "#content",
            "hx-swap": "outerHTML",
        },
    )[
        form_inner_content,
        div(class_="card p-4 flex-row justify-center items-center mt-4")[
            create_button(
                text="Submit",
                variant="primary",
                attrs={"type": "submit"},
            ),
        ],
    ]

    return create_standard_content(
        user_settings=user_settings,
        content=[form_with_buttons],
    )


async def create_llm_models_page(
    user_settings: UserSettings,
    image_base_url_error: str | None = None,
    text_base_url_error: str | None = None,
) -> Element:
    editor = create_llm_editor(
        post_url="/s/user-settings/llm_models",
        initial_image_provider=user_settings.image_model_config.model_provider,
        initial_image_base_url=user_settings.image_model_config.model_base_url,
        initial_image_model=user_settings.image_model_config.model,
        initial_text_provider=user_settings.text_model_config.model_provider,
        initial_text_base_url=user_settings.text_model_config.model_base_url,
        initial_text_model=user_settings.text_model_config.model,
        image_base_url_error=image_base_url_error,
        text_base_url_error=text_base_url_error,
        primary_text="Save",
        cancel_url="/s/user-settings/llm_models",
        hx_target="#content",
        hx_swap="outerHTML",
        show_test_buttons=True,
    )

    return create_standard_content(user_settings=user_settings, content=[editor])


async def create_productivity_page(user_settings: UserSettings) -> Element:
    # user_settings is provided by caller

    form_inner_content = div(class_="card p-6 space-y-6")[
        h2(class_="text-lg font-semibold text-on-surface-strong mb-4")["Productivity"],
        create_markdown_editor(
            element_id="productivity-prompt",
            name="productivity_prompt",
            value=user_settings.productivity_prompt or "",
            placeholder="e.g., How productive was I...",
            title="Productivity Level Prompt",
            height="150px",
        ),
    ]

    form_with_buttons = form(
        element_id="productivity-form",
        method="POST",
        **{
            "hx-post": "/s/user-settings/productivity",
            "hx-target": "#content",
            "hx-swap": "outerHTML",
        },
    )[
        form_inner_content,
        div(class_="card p-4 flex-row justify-around items-center mt-4")[
            create_button(
                text="Cancel",
                variant="destructive",
                attrs={
                    "hx-get": "/s/user-settings/productivity",
                    "hx-target": "#content",
                    "hx-swap": "outerHTML",
                },
            ),
            create_button(
                text="Save",
                variant="primary",
                attrs={"type": "submit"},
                extra_classes="ml-3",
            ),
        ],
    ]

    return create_standard_content(
        user_settings=user_settings,
        content=[form_with_buttons],
    )


async def create_tags_page(conn: aiosqlite.Connection) -> Element:
    """Creates the tags management page using the reusable editor component."""
    user_settings = await select_user_settings(conn)
    assert user_settings is not None, "User settings not found"
    tags = await select_tags(conn) or []
    logger.trace(f"Creating tags page with {len(tags)} tags")

    initial_tags = [
        {
            "id": str(tag.id),
            "name": tag.name,
            "description": tag.description or "",
        }
        for tag in tags
    ]

    content = create_tags_editor(
        initial_tags=initial_tags,
        post_url="/s/tags/update-tags",
        primary_text="Save Tags",
        title="Tags",
        subtitle="Manage tags for categorizing your activities.",
        hx_target="#content",
        hx_swap="outerHTML",
    )

    return create_standard_content(
        user_settings=user_settings,
        content=[content],
    )


def create_status_toggle(is_active: bool, source_id: int) -> Node:
    """Create a toggle switch for source status."""
    return label(class_="label")[
        htpy_input(
            id_=f"source-status-{source_id}",
            class_="input",
            type="checkbox",
            role="switch",
            checked=is_active,
            **{
                "hx-post": f"/s/toggle-source-status/{source_id}",
                "hx-trigger": "change",
                "hx-swap": "outerHTML",
                "x-data": "{}",
            },
        )
    ]


def create_sources_table(
    sources: list[DBDeviceSource], user_timezone: str | None = None
) -> Element:
    """Render the sources table using the shared table component for alignment."""
    tz_str = user_timezone or "UTC"
    now = datetime.now(dt_timezone.utc)

    headers = ["Name", "Type", "Last Seen", "Created", "Status", ""]

    # Empty state
    if not sources:
        return div(
            id="sources-table",
            class_="mx-auto min-w-[theme(screens.md)] w-fit max-w-full rounded-radius border border-outline dark:border-outline-dark overflow-x-auto",
        )[div(class_="p-8 text-center text-muted-foreground")["No sources yet."]]

    return div(
        id="sources-table",
        class_="mx-auto min-w-[theme(screens.md)] w-max table rounded-radius border border-outline dark:border-outline-dark",
    )[
        table(class_="table w-auto mx-auto")[
            thead(
                class_="border-b border-outline bg-surface-alt text-sm text-on-surface-strong dark:border-outline-dark dark:bg-surface-dark-alt dark:text-on-surface-dark-strong"
            )[tr[(th(scope="col", class_="p-4")[h] for h in headers)]],
            tbody(class_="divide-y divide-outline dark:divide-outline-dark")[
                (
                    tr[
                        td(class_="p-4 whitespace-normal break-all")[str(src.name)],
                        td(class_="p-4")[str(src.source_type.value)],
                        td(class_="p-4")[
                            format_recent_or_ordinal(src.last_seen, tz_str, now=now)
                        ],
                        td(class_="p-4")[
                            format_recent_or_ordinal(src.created_at, tz_str, now=now)
                        ],
                        td(class_="p-4")[
                            create_status_toggle(
                                is_active=(src.status == SourceStatus.ACTIVE),
                                source_id=src.id,
                            )
                        ],
                        td(class_="p-4 text-right")[
                            create_button(
                                text=None,
                                variant="destructive",
                                size="sm",
                                icon="delete",
                                attrs={
                                    "type": "button",
                                    "hx-post": f"/s/delete-source/{src.id}",
                                    "hx-target": "#sources-table",
                                    "hx-swap": "outerHTML",
                                },
                            )
                        ],
                    ]
                    for src in sources
                )
            ],
        ]
    ]


async def create_sources_page(conn: aiosqlite.Connection) -> Element:
    """Creates the sources management page with a table of existing sources."""
    user_settings = await select_user_settings(conn)
    assert user_settings is not None, "User settings not found"
    sources = await select_sources(conn)

    # Prepare modal placeholder for Add Source
    add_source_modal = create_generic_modal(
        modal_id="add-source-modal",
        content_id="add-source-modal-content",
        extra_classes="w-full sm:max-w-[425px]",
    )

    content = div(class_="card min-w-[theme(screens.md)] w-fit mx-auto")[
        # Header
        div(class_="p-6 border-b border-outline")[
            h2(class_="text-lg font-semibold text-on-surface-strong")["Sources"],
            p(class_="text-sm text-muted-foreground mt-1")[
                "View and manage data sources."
            ],
        ],
        div(class_="px-6 py-4")[
            create_sources_table(sources, user_timezone=user_settings.timezone),
            # Polling to refresh the table
            div(
                class_="hidden",
                **{
                    "hx-get": "/s/user-settings/sources/table",
                    "hx-trigger": "every 10s",
                    "hx-target": "#sources-table",
                    "hx-swap": "outerHTML",
                },
            ),
        ],
        # Footer with Add Source action
        div(class_="p-4 flex justify-end items-center bg-surface-subtle rounded-b-lg")[
            create_button(
                text="Add Source",
                variant="primary",
                attrs={
                    "type": "button",
                    "hx-get": "/s/add-source-modal",
                    "hx-target": "#add-source-modal-content",
                    "hx-swap": "innerHTML",
                    "onclick": "document.getElementById('add-source-modal').showModal()",
                },
            )
        ],
        add_source_modal,
    ]

    return create_standard_content(
        user_settings=user_settings,
        content=[content],
        inner_classes="mx-auto min-w-[theme(screens.md)] w-fit max-w-full",
    )
