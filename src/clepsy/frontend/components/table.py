from typing import Any, Dict, List

from htpy import Element, div, table, tbody, td, th, thead, tr


def create_table(
    headers: List[str],
    rows: List[List[Any]],
    base_classes_override: str | None = None,
    extra_classes: str | None = None,
    attrs: Dict[str, Any] | None = None,
) -> Element:
    """
    Creates a styled table component based on provided headers and rows.

    Args:
        headers: A list of strings for the table header cells.
        rows: A list of lists, where each inner list represents a row
              and contains the cell data (can be strings or other htpy elements).
        other_classes: Additional CSS classes for the outer div container.
        attrs: Additional HTML attributes for the outer div container.

    Returns:
        An htpy Element representing the table.
    """
    if attrs is None:
        attrs = {}
    user_class = attrs.pop("class", "") or attrs.pop("class_", "") if attrs else ""

    # Outer container div
    # Avoid clipping descendants vertically (charts with rotated labels, tooltips, etc.)
    # Keep horizontal scrolling for wide tables.
    default_base_class = "w-full overflow-x-auto overflow-y-visible rounded-radius border border-outline dark:border-outline-dark"
    base_class = (
        base_classes_override
        if base_classes_override is not None
        else default_base_class
    )
    container_classes = f"{base_class} {extra_classes or ''} {user_class}".strip()

    # Table element
    table_classes = "w-full table"

    # Table head element
    thead_classes = "border-b border-outline bg-surface-alt text-sm text-on-surface-strong dark:border-outline-dark dark:bg-surface-dark-alt dark:text-on-surface-dark-strong"

    tbody_classes = "divide-y divide-outline dark:divide-outline-dark"

    # Header cell class
    th_class = "p-4"

    # Data cell class
    td_class = "p-4"

    return div(class_=container_classes, **attrs)[
        table(class_=table_classes)[
            thead(class_=thead_classes)[
                tr[(th(scope="col", class_=th_class)[header] for header in headers)]
            ],
            tbody(class_=tbody_classes)[
                (tr[(td(class_=td_class)[cell] for cell in row)] for row in rows)
            ],
        ]
    ]
