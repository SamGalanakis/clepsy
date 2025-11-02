from datetime import datetime, timezone

from htpy import Element, div, h2, p, span, table, tbody, td, th, thead, tr

from clepsy.entities import (
    BamlErrorSignal,
    SettingsNotSetSignal,
    WorkerName,
    WorkerSignalBase,
)
from clepsy.frontend.components import (
    create_button,
    create_generic_modal,
    create_standard_content,
)
from clepsy.workers import worker_manager


def _status_badge(running: bool) -> Element:
    cls = "inline-flex items-center rounded px-2 py-0.5 text-xs font-medium " + (
        "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300"
        if running
        else "bg-zinc-200 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200"
    )
    return span(class_=cls)["Running" if running else "Stopped"]


def _format_last_seen(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    now = datetime.now(timezone.utc)
    delta = now - dt
    seconds = int(delta.total_seconds())
    if seconds < 5:
        return "just now"
    if seconds < 60:
        return f"{seconds}s ago"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    # Fallback to ISO date without microseconds
    return dt.replace(microsecond=0).isoformat()


def _get_last_error_time(worker_name: str) -> datetime | None:
    """Return the timestamp of the most recent error signal for a worker.

    Scans the signal queue from newest to oldest and returns the first error's timestamp.
    """
    q = worker_manager.worker_signal_queues.get(worker_name)
    if not q:
        return None

    for sig in reversed(q):
        match sig:
            case BamlErrorSignal() as s:
                return s.timestamp
            case SettingsNotSetSignal() as s:
                return s.timestamp
            case _:
                continue
    return None


def _format_avg_period(seconds: float | None) -> str:
    """Format average period as a rate (x/sec, x/min, x/hr) based on frequency."""
    if seconds is None or seconds <= 0:
        return "—"

    per_sec = 1.0 / seconds
    per_min = 60.0 / seconds
    per_hr = 3600.0 / seconds

    if per_sec >= 1:
        rate, unit = per_sec, "sec"
    elif per_min >= 1:
        rate, unit = per_min, "min"
    else:
        rate, unit = per_hr, "hr"

    shown = f"{rate:.0f}" if rate >= 10 else f"{rate:.1f}"
    return f"{shown}/{unit}"


def create_workers_table_card() -> Element:
    rows: list[Element] = []

    for name, worker in worker_manager.workers.items():
        last_seen = worker_manager.worker_last_success.get(name)
        last_error = _get_last_error_time(name)
        avg_period_s = worker_manager.worker_avg_success_interval_s.get(name)
        rows.append(
            tr[
                td(class_="px-3 py-2 whitespace-nowrap text-sm font-medium")[name],
                td(class_="px-3 py-2 whitespace-nowrap text-sm")[
                    _status_badge(worker.is_running)
                ],
                td(
                    class_="px-3 py-2 whitespace-nowrap text-sm text-on-surface-variant"
                )[_format_last_seen(last_seen)],
                td(
                    class_="px-3 py-2 whitespace-nowrap text-sm text-on-surface-variant"
                )[_format_last_seen(last_error)],
                td(
                    class_="px-3 py-2 whitespace-nowrap text-sm text-on-surface-variant"
                )[_format_avg_period(avg_period_s)],
                td(class_="px-3 py-2 whitespace-nowrap text-sm")[
                    create_button(
                        variant="ghost",
                        text=None,
                        icon="logs",
                        attrs={
                            "title": "View logs",
                            "aria-label": f"View logs for {name}",
                            "hx-get": f"/s/monitoring/workers/logs?name={name}",
                            "hx-target": "#worker-logs-modal-content",
                            "hx-swap": "innerHTML",
                            "onclick": "document.getElementById('worker-logs-modal').showModal()",
                        },
                    )
                ],
            ]
        )

    return div(
        id="workers-table",
        class_="card overflow-hidden",
        hx_get="/s/monitoring/workers/table",
        hx_trigger="every 10s",
        hx_swap="outerHTML",
    )[
        table(class_="min-w-full divide-y divide-border/80")[
            thead(class_="bg-surface-subtle")[
                tr[
                    th(
                        class_="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-on-surface-variant"
                    )["Name"],
                    th(
                        class_="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-on-surface-variant"
                    )["Status"],
                    th(
                        class_="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-on-surface-variant"
                    )["Last seen"],
                    th(
                        class_="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-on-surface-variant"
                    )["Last error"],
                    th(
                        class_="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-on-surface-variant"
                    )["Avg period"],
                    th(
                        class_="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-on-surface-variant"
                    )["Logs"],
                ]
            ],
            tbody(class_="divide-y divide-border")[rows],
        ]
    ]


def create_workers_page() -> Element:
    content = div(class_="container mx-auto max-w-4xl px-4 space-y-4")[
        h2(class_="text-xl font-semibold text-on-surface-strong")["Workers"],
        create_workers_table_card(),
        create_generic_modal(
            modal_id="worker-logs-modal",
            content_id="worker-logs-modal-content",
            extra_classes="w-[95vw] max-w-3xl",
        ),
    ]

    return create_standard_content(user_settings=None, content=content)


def _format_signal_row(signal: WorkerSignalBase) -> Element:
    match signal:
        case BamlErrorSignal() as s:
            ts = s.timestamp.replace(microsecond=0).isoformat()
            return tr[
                td(
                    class_="px-3 py-2 align-top whitespace-nowrap text-xs text-on-surface-variant"
                )[ts],
                td(class_="px-3 py-2 text-sm")[
                    span(
                        class_="inline-flex items-center gap-2 text-red-600 dark:text-red-400"
                    )[
                        span(class_="font-medium")["BAML error"],
                        p(class_="m-0 break-all")[
                            f"{type(s.exception).__name__}: {s.exception}"
                        ],
                    ]
                ],
            ]
        case SettingsNotSetSignal() as s:
            ts = s.timestamp.replace(microsecond=0).isoformat()
            return tr[
                td(
                    class_="px-3 py-2 align-top whitespace-nowrap text-xs text-on-surface-variant"
                )[ts],
                td(class_="px-3 py-2 text-sm")[
                    span(
                        class_="inline-flex items-center gap-2 text-amber-700 dark:text-amber-300"
                    )[
                        span(class_="font-medium")["Settings not set"],
                        p(class_="m-0")[
                            "Worker skipped iteration due to missing settings"
                        ],
                    ]
                ],
            ]
        case _:
            raise RuntimeError(f"Unhandled worker signal type: {type(signal).__name__}")


def create_worker_logs_modal_content(worker_name: WorkerName) -> Element:
    queue = worker_manager.worker_signal_queues.get(worker_name) or []

    header = div(class_="flex justify-between items-center p-4 border-b")[
        h2(class_="text-lg font-semibold text-on-surface")[
            f"Worker logs — {worker_name}"
        ],
        create_button(
            text=None,
            variant="secondary",
            icon="x",
            attrs={
                "onclick": "document.getElementById('worker-logs-modal').close();",
                "aria-label": "Close modal",
            },
        ),
    ]

    if len(queue) == 0:
        body = div(class_="p-4")[
            p(class_="text-sm text-on-surface-variant")["No signals to show"]
        ]
    else:
        rows: list[Element] = []
        for sig in reversed(list(queue)):
            rows.append(_format_signal_row(sig))

        body = div(class_="p-2 max-h-[70dvh] overflow-y-auto")[
            table(class_="min-w-full text-sm")[
                thead[
                    tr[
                        th(
                            class_="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-on-surface-variant"
                        )["Time"],
                        th(
                            class_="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-on-surface-variant"
                        )["Event"],
                    ]
                ],
                tbody[rows],
            ]
        ]

    panel = div(
        class_="bg-surface rounded-lg shadow-lg max-h-[90dvh] overflow-y-auto overflow-x-hidden max-w-full"
    )[
        header,
        body,
    ]
    return panel
