from datetime import datetime, timezone as dt_timezone

import aiosqlite
from htpy import (
    Element,
    Node,
    div,
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

from clepsy.db.queries import select_sources, select_user_settings
from clepsy.entities import DBDeviceSource, SourceStatus
from clepsy.frontend.components import (
    create_button,
    create_generic_modal,
    create_standard_content,
)
from clepsy.utils import format_recent_or_ordinal


def create_status_toggle(is_active: bool, source_id: int) -> Node:
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
    tz_str = user_timezone or "UTC"
    now = datetime.now(dt_timezone.utc)
    headers = ["Name", "Type", "Last Seen", "Created", "Status", ""]
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
                                    "hx-delete": f"/s/sources/{src.id}",
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
    user_settings = await select_user_settings(conn)
    assert user_settings is not None, "User settings not found"
    sources = await select_sources(conn)
    add_source_modal = create_generic_modal(
        modal_id="add-source-modal",
        content_id="add-source-modal-content",
        extra_classes="w-full sm:max-w-[425px]",
    )
    content = div(class_="card min-w-[theme(screens.md)] w-fit mx-auto")[
        div(class_="p-6 border-b border-outline")[
            h2(class_="text-lg font-semibold text-on-surface-strong")["Sources"],
            p(class_="text-sm text-muted-foreground mt-1")[
                "View and manage data sources."
            ],
        ],
        div(class_="px-6 py-4")[
            create_sources_table(sources, user_timezone=user_settings.timezone),
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
