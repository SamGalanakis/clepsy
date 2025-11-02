from __future__ import annotations

import json

from htpy import (
    Element,
    div,
    form,
    h2,
    input as htpy_input,
    p,
    style,
    template,
)

from clepsy.frontend.components import (
    create_button,
    create_text_input,
    create_tooltip,
)


def create_tags_editor(
    *,
    initial_tags: list[dict],
    post_url: str,
    primary_text: str = "Save Tags",
    back_url: str | None = None,
    cancel_url: str | None = None,
    include_skip: bool = False,
    hx_target: str = "#content",
    hx_swap: str = "outerHTML",
    title: str = "Tags",
    subtitle: str | None = "Manage tags for categorizing your activities.",
) -> Element:
    tags_json = json.dumps(initial_tags)

    alpine_data = f"""{{
        tags: {tags_json},
        addNewTag() {{
            this.tags.push({{ id: 'new-' + Date.now(), name: '', description: '' }});
            this.$nextTick(() => {{
                const newTagInput = this.$el.querySelector('input[x-model=\"tag.name\"]:last-of-type');
                if (newTagInput) newTagInput.focus();
            }});
        }},
        removeTag(index) {{
            this.tags.splice(index, 1);
        }},
        submitForm() {{
            document.getElementById('tags-data-input').value = JSON.stringify(this.tags);
        }}
    }}"""

    return div(class_="card")[
        # Header
        div(
            class_="p-6 border-b border-outline flex items-start justify-between gap-4"
        )[
            div[
                h2(class_="text-lg font-semibold text-on-surface-strong")[title],
                p(class_="text-sm text-muted-foreground mt-1")[subtitle]
                if subtitle
                else None,
            ],
            create_tooltip(
                button_text="i",
                tooltip_text=(
                    "Editing an existing tag will keep the association with previously tagged activities. "
                    "If you want to significantly change the spirit of a tag, create a new tag and delete the old one."
                ),
                side="top",
                align="end",
            ),
        ],
        div(**{"x-data": alpine_data, "x-cloak": "true"})[
            form(
                element_id="tags-form",
                method="POST",
                **{
                    "hx-post": post_url,
                    "hx-target": hx_target,
                    "hx-swap": hx_swap,
                    "@submit": "submitForm()",
                },
            )[
                htpy_input(
                    type="hidden",
                    name="tags_data",
                    id_="tags-data-input",
                    **{"x-effect": "$el.value = JSON.stringify(tags)"},
                ),
                # Table
                div(class_="divide-y divide-outline")[
                    div(
                        class_="p-4 grid grid-cols-[1fr_2fr_auto] gap-4 text-sm font-medium text-muted-foreground",
                    )[
                        div["Name"],
                        div["Description"],
                        div(class_="w-12"),
                    ],
                    div(class_="max-h-[400px] overflow-y-auto")[
                        template(**{"x-for": "(tag, index) in tags", ":key": "tag.id"})[
                            div(
                                class_="p-4 grid grid-cols-[1fr_2fr_auto] gap-4 items-start hover:bg-surface-hover",
                            )[
                                div[
                                    create_text_input(
                                        placeholder="Tag name",
                                        required=True,
                                        attrs={"x-model": "tag.name", "type": "text"},
                                    ),
                                ],
                                create_text_input(
                                    placeholder="Optional description",
                                    attrs={
                                        "x-model": "tag.description",
                                        "type": "text",
                                    },
                                ),
                                create_button(
                                    text=None,
                                    variant="destructive",
                                    size="sm",
                                    icon="delete",
                                    attrs={
                                        "@click.prevent": "removeTag(index)",
                                        "type": "button",
                                    },
                                ),
                            ]
                        ],
                        div(
                            class_="p-8 text-center text-muted-foreground",
                            **{"x-show": "tags.length === 0"},
                        )["No tags yet. Add one to get started!",],
                    ],
                ],
                # Error container for htmx responses
                div(element_id="tags-error-container"),
                # Footer
                div(
                    class_="p-4 flex justify-between items-center bg-surface-subtle rounded-b-lg"
                )[
                    create_button(
                        text="Add Tag",
                        variant="outline",
                        icon="plus",
                        attrs={"@click.prevent": "addNewTag()"},
                    ),
                    div(class_="flex items-center gap-3")[
                        create_button(
                            text="Back",
                            variant="secondary",
                            attrs={
                                "type": "button",
                                "hx-get": back_url,
                                "hx-target": hx_target,
                                "hx-swap": hx_swap,
                            },
                        )
                        if back_url
                        else None,
                        create_button(
                            text="Cancel",
                            variant="destructive",
                            attrs={
                                "type": "button",
                                "hx-get": cancel_url,
                                "hx-target": hx_target,
                                "hx-swap": hx_swap,
                            },
                        )
                        if cancel_url
                        else None,
                        create_button(
                            text="Skip" if include_skip else None,
                            variant="secondary",
                            attrs={
                                "type": "submit",
                                "name": "action",
                                "value": "skip",
                            },
                        )
                        if include_skip
                        else None,
                        create_button(
                            text=primary_text,
                            variant="primary",
                            attrs={"type": "submit"},
                        ),
                    ],
                ],
            ],
        ],
        style["[x-cloak] { display: none !important; }"],
    ]
