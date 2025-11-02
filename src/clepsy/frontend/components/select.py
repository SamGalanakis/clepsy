from typing import Any, Mapping

from htpy import (
    Element,
    button,
    div,
    input as htpy_input,
    label,
    option,
    select,
    span,
    template,
)
from markupsafe import Markup

from clepsy import utils

from .icons import get_icon_svg


def create_multiselect(
    element_id: str | None,
    title: str | None,
    name: str | None,
    label_to_val: dict[str, str],
    selected_labels: list[str],
    x_model: str | None = None,
    button_attrs_update: dict | None = None,
    container_attrs_update: dict | None = None,
    outer_div_attrs_update: dict | None = None,
) -> Element:
    base_button_attrs = {
        "x-on:click": "open",
        "aria-haspopup": "listbox",
        "x-bind:aria-expanded": "isOpen()",
        "class": "btn-outline justify-between font-normal w-full",
    }
    if button_attrs_update:
        # Shallow merge; caller can override class if desired
        base_button_attrs.update(button_attrs_update)
    container_class = "multi-select relative w-full"

    x_model_str = f"{x_model} =  this.selectedValues();" if x_model else ""
    x_data_str = f"""{{
        options: [],
        selected: [],
        show: false,
        open() {{ this.show = true }},
        close() {{ this.show = false }},
        isOpen() {{ return this.show === true }},
        select(index, event) {{
            if (!this.options[index].selected) {{
                this.options[index].selected = true;
                this.selected.push(index);
            }} else {{
                this.selected.splice(this.selected.lastIndexOf(index), 1);
                this.options[index].selected = false;
            }}
            this.$dispatch('multiselect-change', {{ value: this.selectedValues() }});
            {x_model_str}
        }},
        loadOptions() {{
            const options = document.getElementById('{element_id}-select').options;
            for (let i = 0; i < options.length; i++) {{
                this.options.push({{
                    value: options[i].value,
                    text: options[i].innerText,
                    selected: options[i].selected
                }});
            }}
            this.selected = this.options.map((opt, i) => opt.selected ? i : null).filter(i => i !== null);
        }},
        selectedValues() {{
            return this.selected.map(i => this.options[i].value);
        }}
    }}"""

    base_container_attrs = {
        "x-cloak": True,
        "x-data": x_data_str,
        "x-init": "loadOptions()",
        "class": container_class,
    }
    if container_attrs_update:
        base_container_attrs.update(container_attrs_update)

    hidden_select = select(
        id=f"{element_id}-select",
        class_="hidden",
        multiple=True,
    )[
        *[
            option(value=val, selected=(label_text in selected_labels))[label_text]
            for label_text, val in label_to_val.items()
        ]
    ]

    component = div(
        **base_container_attrs,
    )[
        # Create multiple hidden inputs with the same name for array submission
        template(**{"x-for": "value in selectedValues()", "x-bind:key": "value"})[
            htpy_input(name=name, type="hidden", **{"x-bind:value": "value"})
        ],
        button(
            type="button",
            **base_button_attrs,
        )[
            span(
                **{
                    "x-show": "selected.length > 0",
                    "x-text": "selected.map(i => options[i].text).join(', ')",
                },
                class_="truncate",
            ),
            span(
                **{"x-show": "selected.length == 0"},
                class_="text-muted-foreground truncate",
            )["Select options..."],
            # Chevron icon wrapped to match single-select (muted + opacity)
            span(
                class_="text-muted-foreground opacity-50 shrink-0",
            )[get_icon_svg("chevrons-up-down")],
        ],
        div(
            **{
                "x-show.transition.origin.top": "isOpen()",
                "x-on:click.outside": "close",
                "data-popover": True,
                "x-bind:aria-hidden": "!isOpen()",
            },
            class_="multi-select-dropdown absolute top-full left-0 right-0 mt-1",
        )[
            div(
                **{"role": "listbox", "aria-orientation": "vertical"},
                class_="bg-popover text-popover-foreground border border-border rounded-md shadow-lg p-1",
            )[
                template(
                    **{"x-for": "(option,index) in options", "x-bind:key": "index"},
                )[
                    div(
                        **{
                            "role": "option",
                            "@click": "select(index,$event)",
                            "x-bind:data-value": "option.value",
                            "x-bind:aria-selected": "option.selected",
                            "x-bind:class": "option.selected ? 'selected' : ''",
                        },
                        class_="multi-select-option",
                    )[span(**{"x-text": "option.text"}),]
                ]
            ],
        ],
    ]

    final_outer_classes = "flex min-w-0 w-full flex-col gap-2"
    outer_div_attrs = {"class": final_outer_classes}
    if outer_div_attrs_update:
        outer_div_attrs.update(outer_div_attrs_update)
    return div(**outer_div_attrs)[
        label(for_=element_id, class_="label")[title] if title else "",
        hidden_select,
        component,
    ]


def create_search_element(placeholder: str, listbox_id: str) -> Markup:
    return Markup(
        f"""<header class="p-2">
      <input type="text" value="" placeholder="{placeholder}" autocomplete="off" autocorrect="off" spellcheck="false" aria-autocomplete="list" role="combobox" aria-expanded="false" aria-controls="{listbox_id}" aria-labelledby="{listbox_id}-trigger" class="w-full input border border-border rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1 focus:ring-offset-background"/>
    </header>"""
    )


def create_single_select(
    element_id: str,
    name: str,
    title: str | None,
    options: Mapping[str, int | str],
    selected_val: str | None,
    x_model: str | None = None,
    placeholder_text="Please Select",
    placeholder_value: str = "",
    button_attrs_update: dict[str, Any] | None = None,
    include_search: bool = False,
    outer_div_attrs_update: dict[str, Any] | None = None,
    main_div_args_update: dict[str, Any] | None = None,
    hidden_input_attrs_update: dict[str, Any] | None = None,
) -> Element:
    """
    Creates a styled single-select dropdown component using Basecoat UI pattern.
    """

    default_outer_div_class = "flex w-full flex-col gap-2"

    outer_div_attrs = {
        "class": default_outer_div_class,
    }

    outer_div_attrs.update(outer_div_attrs_update or {})

    selected_text = placeholder_text

    if selected_val:
        for label_text, val in options.items():
            if str(val) == str(selected_val):
                selected_text = label_text
                break
        else:
            raise ValueError(f"selected_val '{selected_val}' not found in options")

    x_data_str = """
    {
        selected_val: '[[$selected_val]]',
        show: false,
        open() { this.show = true },
        close() { this.show = false },
        isOpen() { return this.show === true },
        select(value, text) {
            this.selected_val = value;
            this.$refs.hiddenInput.value = value;
            this.$refs.button.querySelector('.truncate').textContent = text;
            this.close();
            this.$dispatch('change', { value: value });
        }
    }"""

    x_data_str = utils.substitute_template(
        x_data_str,
        {
            "selected_val": selected_val
            if selected_val is not None
            else placeholder_value,
        },
    )

    main_div_args: dict[str, Any] = {"class": "select"}

    if x_model:
        main_div_args["@change"] = f"{x_model} = $event.detail.value;"

    main_div_args.update(main_div_args_update or {})

    button_attrs = {
        "aria-haspopup": "listbox",
        "aria-expanded": "false",
        "aria-controls": f"{element_id}-listbox",
        "class": "btn-outline justify-between font-normal w-full",
        "type": "button",
    }
    button_attrs.update(button_attrs_update or {})

    search_element = None
    if include_search:
        search_element = create_search_element(
            placeholder="Search...",
            listbox_id=f"{element_id}-listbox",
        )

    hidden_input_attrs = {
        "x_data": x_data_str,
        "name": name,
        "type": "hidden",
        "id": f"{element_id}-hidden-input",
        "value": selected_val,
    }
    if hidden_input_attrs_update:
        hidden_input_attrs.update(hidden_input_attrs_update)

    return div(**outer_div_attrs)[
        label(for_=element_id, class_="label")[title] if title else "",
        div(id=element_id, **main_div_args)[
            button(**button_attrs)[
                span(class_="truncate")[selected_text],
                span(
                    class_="text-muted-foreground opacity-50 shrink-0",
                )[get_icon_svg("chevrons-up-down")],
            ],
            div(
                **{"data-popover": True, "aria-hidden": "true"},
                class_="absolute top-full left-0 right-0 z-55 mt-1",
            )[
                div(
                    **{
                        "role": "listbox",
                        "id": f"{element_id}-listbox",
                        "aria-orientation": "vertical",
                    },
                    class_="bg-popover text-popover-foreground border border-border rounded-md shadow-lg p-1 max-h-60 overflow-y-auto",
                )[
                    search_element,
                    *[
                        div(
                            **{
                                "role": "option",
                                "data-value": str(val),
                                "aria-selected": "true"
                                if str(val) == str(selected_val)
                                else "false",
                            }
                        )[label_text]
                        for label_text, val in options.items()
                    ],
                ]
            ],
            htpy_input(**hidden_input_attrs),
        ],
    ]
