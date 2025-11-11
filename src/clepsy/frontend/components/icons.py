from typing import Literal

from markupsafe import Markup


IconName = Literal[
    "logs",
    "drag_handle",
    "delete",
    "chevron-left",
    "chevron-right",
    "chevrons-up-down",
    "sidebar_toggle",
    "copy",
    "refresh",
    "pause-circle",
    "play",
    "pause",
    "ellipsis_vertical",
    "settings",
    "x",
    "tick",
    "warning",
    "rotate_ccw",
    "rotate_cw",
    "chevron_up",
    "chevron_down",
    "clepsy_logo",
    "goal",
    "chart-column",
    "pulse",
    "pickaxe",
    "plus",
]


chart_column = Markup(
    """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-chart-column-icon lucide-chart-column"><path d="M3 3v16a2 2 0 0 0 2 2h16"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/></svg>"""
)

delete_icon = Markup(
    """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-trash-icon lucide-trash"><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>"""
)
chevron_right_svg = Markup(
    """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-chevron-right-icon lucide-chevron-right"><path d="m9 18 6-6-6-6"/></svg>"""
)
chevron_left_svg = Markup(
    """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-chevron-left-icon lucide-chevron-left"><path d="m15 18-6-6 6-6"/></svg>"""
)


pulse_svg = Markup(
    """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-activity-icon lucide-activity"><path d="M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2"/></svg>"""
)

pickaxe_svg = Markup(
    """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-pickaxe-icon lucide-pickaxe"><path d="m14 13-8.381 8.38a1 1 0 0 1-3.001-3L11 9.999"/><path d="M15.973 4.027A13 13 0 0 0 5.902 2.373c-1.398.342-1.092 2.158.277 2.601a19.9 19.9 0 0 1 5.822 3.024"/><path d="M16.001 11.999a19.9 19.9 0 0 1 3.024 5.824c.444 1.369 2.26 1.676 2.603.278A13 13 0 0 0 20 8.069"/><path d="M18.352 3.352a1.205 1.205 0 0 0-1.704 0l-5.296 5.296a1.205 1.205 0 0 0 0 1.704l2.296 2.296a1.205 1.205 0 0 0 1.704 0l5.296-5.296a1.205 1.205 0 0 0 0-1.704z"/></svg>"""
)


logo_svg = Markup("""
<svg
   version="1.1"
   id="svg1"
   width="106.29333"
   height="153.36"
   viewBox="0 0 106.29333 153.36001"
   class="h-8 w-8"
   xmlns="http://www.w3.org/2000/svg"
   xmlns:svg="http://www.w3.org/2000/svg">
  <defs
     id="defs1" />
  <g
     id="g1"
     class="fill-black dark:fill-white"
     transform="translate(-2031.8064,-533.46944)">
    <g
       id="group-R5"
       transform="translate(58.286435,-8.0238736)">
      <path id="path24" d="m 15037.8,4996.05 v -103.47 h -60 v 103.47 h 60" style="fill:currentColor;fill-opacity:1;fill-rule:nonzero;stroke:none" transform="matrix(0.13333333,0,0,-0.13333333,0,1333.3333)" />
      <path id="path25" d="m 15128.9,5058.96 v -166 h -60.1 v 166 h 60.1" style="fill:currentColor;fill-opacity:1;fill-rule:nonzero;stroke:none" transform="matrix(0.13333333,0,0,-0.13333333,0,1333.3333)" />
      <path id="path26" d="m 15311.2,5120.1 v -226.63 h -60.1 v 226.63 h 60.1" style="fill:currentColor;fill-opacity:1;fill-rule:nonzero;stroke:none" transform="matrix(0.13333333,0,0,-0.13333333,0,1333.3333)" />
      <path id="path27" d="m 15311.1,5088.26 v -194.54 h -60 v 194.54 h 60" style="fill:currentColor;fill-opacity:1;fill-rule:nonzero;stroke:none" transform="matrix(0.13333333,0,0,-0.13333333,0,1333.3333)" />
      <path id="path28" d="m 15220,5184.78 v -291.06 h -60 v 291.06 h 60" style="fill:currentColor;fill-opacity:1;fill-rule:nonzero;stroke:none" transform="matrix(0.13333333,0,0,-0.13333333,0,1333.3333)" />
      <path id="path29" d="m 15402.2,5000 v -107.04 h -60 V 5000 h 60" style="fill:currentColor;fill-opacity:1;fill-rule:nonzero;stroke:none" transform="matrix(0.13333333,0,0,-0.13333333,0,1333.3333)" />
      <path id="path30" d="m 15427.2,5705.4 -151.5,-216.1 -31.2,-44.5 -13.2,-18.9 c -4,-5.6 -7,-11.8 -9.1,-18.3 -2,-6.5 -3.1,-13.3 -3.1,-20.2 v -66.7 c -11.8,-8 -26.9,-18.3 -38.7,-26.7 v 92.4 c 0,13.7 -4.3,27.2 -12.2,38.4 l -0.7,1.1 -15,21.4 -31.2,44.5 -92,131.2 -31.1,44.5 -23.8,34 c 43.5,4 116,2.2 210.8,-29.9 102.8,-34.8 191.5,2.4 242,33.8" style="fill:currentColor;fill-opacity:1;fill-rule:nonzero;stroke:none" transform="matrix(0.13333333,0,0,-0.13333333,0,1333.3333)" />
      <path id="path80" style="fill:currentColor;fill-opacity:1;fill-rule:nonzero;stroke:none" d="m 15598.6,4840 v -51.4 h -797.2 v 51.4 c 0,17.7 14.4,32.1 32.1,32.1 h 7.2 680.2 45.6 c 17.7,0 32.1,-14.4 32.1,-32.1" transform="matrix(0.13333333,0,0,-0.13333333,0,1333.3333)" />
      <path id="path77" style="fill:currentColor;fill-opacity:1;fill-rule:nonzero;stroke:none" d="m 14801.4,5938.8 v -51.4 c 0,-17.7 14.4,-32.1 32.1,-32.1 h 45.6 680.2 7.2 c 17.7,0 32.1,14.4 32.1,32.1 v 51.4 z" transform="matrix(0.13333333,0,0,-0.13333333,0,1333.3333)" />
      <path id="path76" style="fill:currentColor;fill-opacity:1;fill-rule:nonzero;stroke:none" d="m 15543,5003.5 -0.3,0.4 -235.8,339.3 c -8.6,12.3 -8.6,28.8 0,41 l 235.5,338.8 0.6,1 c 10.7,17.4 16.3,37.7 16.3,58.6 v 55.8 h -38.4 v -55.8 c 0,-13.6 -3.6,-26.8 -10.4,-38.1 l -235.2,-338.3 c -17.6,-25.4 -17.6,-59.5 0,-84.9 l 235.2,-338.3 c 6.8,-11.4 10.4,-24.5 10.4,-38.2 v -55.7 h 38.4 v 55.7 c 0,20.9 -5.6,41.2 -16.3,58.7 z" transform="matrix(0.13333333,0,0,-0.13333333,0,1333.3333)" />
      <path id="path31" style="fill:currentColor;fill-opacity:1;fill-rule:nonzero;stroke:none" d="m 14889.5,5744.5 c -6.8,11.3 -10.4,24.5 -10.4,38.1 v 55.8 h -38.4 v -55.8 c 0,-20.9 5.7,-41.2 16.3,-58.6 l 0.3,-0.5 235.8,-339.3 c 8.6,-12.2 8.6,-28.7 0,-41 l -235.5,-338.8 -0.6,-1 c -10.6,-17.4 -16.3,-37.7 -16.3,-58.6 v -55.7 h 38.4 v 55.7 c 0,13.7 3.6,26.8 10.4,38.2 l 235.2,338.3 c 17.6,25.4 17.6,59.5 0,84.9 z" transform="matrix(0.13333333,0,0,-0.13333333,0,1333.3333)" />
    </g>
  </g>
</svg>
""")

# Define the drag handle SVG structure using htpy elements
# Use fill="currentColor" and theme-aware text classes for dynamic color
drag_handle = Markup(
    """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-grip-vertical-icon lucide-grip-vertical"><circle cx="9" cy="12" r="1"/><circle cx="9" cy="5" r="1"/><circle cx="9" cy="19" r="1"/><circle cx="15" cy="12" r="1"/><circle cx="15" cy="5" r="1"/><circle cx="15" cy="19" r="1"/></svg>"""
)


chevrons_up_down_icon = Markup(
    """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-chevrons-up-down-icon lucide-chevrons-up-down"><path d="m7 15 5 5 5-5"/><path d="m7 9 5-5 5 5"/></svg>"""
)


copy_svg = Markup(
    """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-copy-icon lucide-copy"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>"""
)


refresh_svg = Markup(
    """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-refresh-ccw-icon lucide-refresh-ccw"><path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 16h5v5"/></svg>"""
)


pause_circle = Markup(
    """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-circle-pause-icon lucide-circle-pause"><circle cx="12" cy="12" r="10"/><line x1="10" x2="10" y1="15" y2="9"/><line x1="14" x2="14" y1="15" y2="9"/></svg>"""
)

play = Markup(
    """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-play-icon lucide-play"><path d="M5 5a2 2 0 0 1 3.008-1.728l11.997 6.998a2 2 0 0 1 .003 3.458l-12 7A2 2 0 0 1 5 19z"/></svg>"""
)


pause = Markup(
    """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-pause-icon lucide-pause"><rect x="14" y="3" width="5" height="18" rx="1"/><rect x="5" y="3" width="5" height="18" rx="1"/></svg>"""
)


ellipsis_vertical = Markup(
    """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-ellipsis-vertical-icon lucide-ellipsis-vertical"><circle cx="12" cy="12" r="1"/><circle cx="12" cy="5" r="1"/><circle cx="12" cy="19" r="1"/></svg>"""
)

settings = Markup(
    """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-settings-icon lucide-settings"><path d="M9.671 4.136a2.34 2.34 0 0 1 4.659 0 2.34 2.34 0 0 0 3.319 1.915 2.34 2.34 0 0 1 2.33 4.033 2.34 2.34 0 0 0 0 3.831 2.34 2.34 0 0 1-2.33 4.033 2.34 2.34 0 0 0-3.319 1.915 2.34 2.34 0 0 1-4.659 0 2.34 2.34 0 0 0-3.32-1.915 2.34 2.34 0 0 1-2.33-4.033 2.34 2.34 0 0 0 0-3.831A2.34 2.34 0 0 1 6.35 6.051a2.34 2.34 0 0 0 3.319-1.915"/><circle cx="12" cy="12" r="3"/></svg>"""
)

x_icon = Markup(
    """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-x-icon lucide-x"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>"""
)


tick = Markup(
    """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-check-icon lucide-check"><path d="M20 6 9 17l-5-5"/></svg>"""
)

warning = Markup(
    """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-triangle-alert-icon lucide-triangle-alert"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>"""
)

rotate_ccw = Markup(
    """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-rotate-ccw-icon lucide-rotate-ccw"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>"""
)

rotate_cw = Markup(
    """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-rotate-cw-icon lucide-rotate-cw"><path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/></svg>"""
)

chevron_up = Markup(
    """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-chevron-up-icon lucide-chevron-up"><path d="m18 15-6-6-6 6"/></svg>"""
)

chevron_down = Markup(
    """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-chevron-down-icon lucide-chevron-down"><path d="m6 9 6 6 6-6"/></svg>"""
)


plus_svg = Markup(
    """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-plus-icon lucide-plus"><path d="M5 12h14"/><path d="M12 5v14"/></svg>"""
)


logs_svg = Markup(
    """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-logs-icon lucide-logs"><path d="M3 5h1"/><path d="M3 12h1"/><path d="M3 19h1"/><path d="M8 5h1"/><path d="M8 12h1"/><path d="M8 19h1"/><path d="M13 5h8"/><path d="M13 12h8"/><path d="M13 19h8"/></svg>"""
)


goal_svg = Markup(
    """
<svg xmlns="http://www.w3.org/2000/svg"
         viewBox="0 0 24 24"
         class="w-5 h-5 flex-none"
         fill="none"
         stroke="currentColor"
         stroke-linecap="round"
         stroke-linejoin="round"
         stroke-width="2">
    <path d="M12 13V2l8 4-8 4"/>
    <path d="M20.561 10.222a9 9 0 1 1-12.55-5.29"/>
    <path d="M8.002 9.997a5 5 0 1 0 8.9 2.02"/>
</svg>
"""
)


def get_icon_svg(
    icon_name: IconName,
) -> Markup:
    match icon_name:
        case "plus":
            icon = plus_svg
        case "drag_handle":
            icon = drag_handle
        case "delete":
            icon = delete_icon
        case "chevron-left":
            icon = chevron_left_svg
        case "chevron-right":
            icon = chevron_right_svg
        case "chevrons-up-down":
            icon = chevrons_up_down_icon

        case "sidebar_toggle":
            icon = Markup(
                """<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"24\" height=\"24\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\" class=\"lucide lucide-layout-panel-left\"><rect width=\"18\" height=\"18\" x=\"3\" y=\"3\" rx=\"2\"/><path d=\"M9 3v18\"/></svg>"""
            )

        case "copy":
            icon = copy_svg
        case "refresh":
            icon = refresh_svg
        case "pause_circle":
            icon = pause_circle
        case "play":
            icon = play
        case "pause":
            icon = pause
        case "ellipsis_vertical":
            icon = ellipsis_vertical
        case "settings":
            icon = settings
        case "x":
            icon = x_icon
        case "tick":
            icon = tick

        case "warning":
            icon = warning

        case "rotate_ccw":
            icon = rotate_ccw
        case "rotate_cw":
            icon = rotate_cw

        case "chevron_up":
            icon = chevron_up
        case "chevron_down":
            icon = chevron_down

        case "clepsy_logo":
            icon = logo_svg
        case "goal":
            icon = goal_svg
        case "chart-column":
            icon = chart_column
        case "pulse":
            icon = pulse_svg
        case "pickaxe":
            icon = pickaxe_svg
        case "logs":
            icon = logs_svg
        case _:
            raise ValueError(f"Unsupported icon name: {icon_name}")

    return icon
