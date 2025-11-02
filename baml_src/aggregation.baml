class RelativeTimestamp {
  minutes int
  seconds int
}



type ActivityEventType = "open" | "close"

class ActivityMetadata {
  name        string
  description string
  @description("Description of the activity.")
}



type TimelineLogType = "desktop_screenshot" | "mobile_app_usage"


class DesktopCheckScreenshotVLM {
  kind "desktop_screenshot_vlm"
  llm_description string
  active_window  WindowInfo
  timestamp RelativeTimestamp

}

class DesktopCheckScreenshotOCR {
  kind "desktop_screenshot_ocr"
  image_text string
  active_window  WindowInfo
  timestamp RelativeTimestamp
  image_text_post_processed_by_llm bool
}

class MobileAppUsageEvent {
  kind "mobile_app_usage"
  package_name string
  app_label string
  timestamp RelativeTimestamp
  activity_name string?
  media_summary string?
  notification_text string?
}

type TimelineLog = MobileAppUsageEvent | DesktopCheckScreenshotVLM | DesktopCheckScreenshotOCR



template_string FormatMobileAppUsageLog(log: MobileAppUsageEvent) #"
Mobile App Usage Log
Time: {{ log.timestamp.minutes}}m{{ log.timestamp.seconds}}s
App Label: {{ log.app_label }}
Package Name: {{ log.package_name }}
{% if log.activity_name %}Activity Name: {{ log.activity_name }}{% endif %}
{% if log.media_summary %}Media: {{ log.media_summary }}{% endif %}
{% if log.notification_text %}Notification: {{ log.notification_text }}{% endif %}
"#

template_string FormatDesktopCheckScreenshotVLMLog(log: DesktopCheckScreenshotVLM) #""
Computer Screenshot Log
Time: {{ log.timestamp.minutes}}m{{ log.timestamp.seconds}}s
Application Name: {{ log.active_window.app_name }}
Window Title: {{ log.active_window.title }}
Image description: {{ log.llm_description }}
"#

template_string FormatDesktopCheckScreenshotOCRLog(log: DesktopCheckScreenshotOCR) #""
Computer Screenshot Log
Time: {{ log.timestamp.minutes}}m{{ log.timestamp.seconds}}s
Application Name: {{ log.active_window.app_name }}
Window Title: {{ log.active_window.title }}
{% if log.image_text_post_processed_by_llm %}
Image description: {{ log.image_text }}
{% else %}
Text from OCR extraction: {{ log.image_text }}
{% endif %}
"#





template_string FormattedLogsList( logs: TimelineLog[] ) #"
{%- for log in logs %}
{{ loop.index }}. {%- if log.kind == "mobile_app_usage" %}
{{ FormatMobileAppUsageLog(log) }}
{%- elif log.kind == "desktop_screenshot_vlm" %}
{{ FormatDesktopCheckScreenshotVLMLog(log) }}
{%- elif log.kind == "desktop_screenshot_ocr" %}
{{ FormatDesktopCheckScreenshotOCRLog(log) }}
{%- endif %}

{%- endfor %}
"#

class Event {
  activity_id string
  @description("Must match activity id. Should be a lower-snake-case slug")
  t  string
  @description("Timestamp of the event, relative to the start of the aggregaton period in the format <minutes>m<seconds>s.")

  event_type ActivityEventType
}


class Timeline  {
    @@dynamic

  events Event[]
    @description("List of all events in the timeline")

  activities map<string, ActivityMetadata>
    @description("Map of activity IDs to their metadata, including name and description. Must match activity_id  of corresponding events. Should be a lower-snake-case slug.")
}

class TimelineWithReasoning {
   reasoning string
    @description("Reasoning behind the generated timeline, explaining the decisions made.")
  filled_schema Timeline
    @description("The generated timeline of activities.")

}







template_string TIMELINE_GENERATION_PROMPT(
max_pause_time_seconds:int,
logs: TimelineLog[],
duration_seconds: int,
max_desktop_screenshot_log_interval_seconds: int
) #"
{{ _.role("system") }}
You are an expert timeline generator. Your task is to create a structured timeline of user activities based on the provided summary and context.
You will be given a list of timestamped logs gathered over a period of {{duration_seconds}} seconds.
The log timestamps are relative to the start of the aggregation period in the format <minutes>m<seconds>s. For example, '1m30s' means 1 minute and 30 seconds after the start of the aggregation period. Do not use zero padding.
The output timeline should also use relative timestamps in the same format.
The generated timeline will be used for a time tracking application that the user uses to track their activities.

**Follow these rules:**

## What logs mean:

1. Computer screenshot logs
  1. These logs indicate what the user was doing on their computer at a specific time point — extracted via screenshot.
  2. Logs are not continuous; they are discrete snapshots at specific times, expected to be at most roughly {{max_desktop_screenshot_log_interval_seconds}} seconds apart.
  3. The user may have been doing something else between logs, but you have no information about that.
  4. Successive logs close to each other likely indicate the user was engaged in that activity during the interval.
  5. A lack of logs for more than a few seconds beyond {{max_desktop_screenshot_log_interval_seconds}} indicates inactivity — no computer activity should be created for that period.

Mobile app usage logs capture activity from the user's phone and complement desktop context:
- Treat them as signals that the user was focused on the referenced app around the timestamp.
- Use the package name and app label to infer activity intent; incorporate `activity_name`, `media_summary`, or `notification_text` details when present.
- They may overlap with desktop work (e.g., multitasking on phone and computer). Reflect multitasking only when the combined evidence makes sense.
- Absence of screenshot imagery means you must lean on the textual metadata; avoid inventing details that are not implied by the log.

## Activity Definition

1. **Name** — short, high-level, captures the core of the activity.
2. **Activity ID** — lower-snake_case slug, descriptive (e.g. `vscode_coding`, `youtube_break`).
3. **Description** — 1-2 sentences (no sensitive info) giving a concise overview.

---

## Single-Activity Event Rules

1. Events are either **OPEN** or **CLOSE**.
2. **OPEN** = start / resume.
3. **CLOSE** = pause / end.
4. The first event must always be **OPEN**.
5. NEVER have two consecutive events of the same type (e.g. two **START** events in a row).
6. Last event **CLOSE** ⇒ activity is *paused*.
7. Pauses may last **max {{max_pause_time_seconds}} seconds**.
8. Therefore, a **CLOSE** must be followed by an **OPEN** within **{{max_pause_time_seconds}} seconds**.
9. After **{{max_pause_time_seconds}} seconds** without an **OPEN**, the activity is *permanently closed*.
10. Events near the aggregation period's end are not special-cased.
11. **Do not** add artificial **CLOSE** events at aggregation boundaries.
12. Leaving an activity with a final **OPEN** simply means it continues for the rest of the period.
13. Lack of logs during a time period should **NOT** be represented as an activity.


---

## Relevant Activities

1. Logs related to things like the user using OS search, or system notifications, should not be included as activities
  unless they are significant enough to warrant their own activity.


---

## Multi-Activity Rules

1. Activities **may overlap** but only if they truly do so, as in the user is genuinely multitasking.
2. If one activity directly follows another, the **CLOSE** timestamp of the first should equal the **OPEN** timestamp of the second.
3. Activities should only overlap if the user is multitasking and the activities are distinct enough to warrant separate entries.
4. Multitasking is rare, so avoid it unless the logs clearly indicate it.
5. Do not make overlapping activities for different aspects of the same task (e.g. debugging in VSCode and asking AI about a bug in VSCode).
6. Do not make overlapping activities for more specific tasks that are part of a larger task (e.g. coding in VSCode and creating tests).


## Granularity & Context Switching

### Hard boundaries — start a new activity

1. **App change** (IDE ↔ Browser, Editor ↔ Video, etc.).
2. **Domain family change** in a browser (e.g., `bbc.co.uk` → `economist.com`).
3. **Artifact change within the same app/website**:
  1. Repo/workspace change (VSCode).
  2. Document change (Word/Notion).
  3. Different game in a launcher.
4. **Category flip** within the same app (e.g., Work ↔ Social/Entertainment/Personal).

**Group together — do not start a new activity**

1. SSO/auth (`accounts.google.com`, `auth0.com`), CDNs/trackers (`gstatic.com`, `cloudfront.net`, `doubleclick.net`), link shorteners (`t.co`, `bit.ly`), payment popups.
2. Attribute their time to the **final destination** domain.
3. On websites with variable content, like news sites or YouTube:
  1. If the user stays on the same domain family and topic (e.g., reading multiple articles on `nytimes.com` about politics), group together as one activity.
  2. If the user switches to a different topic (e.g., from politics to sports), start a new activity.
  3. Similarly for YouTube, if the user watches multiple videos in the same category (e.g., tech reviews), group together; if they switch categories (e.g., from tech reviews to music videos), start a new activity.
  4. If constantly changing topics/domains (e.g., browsing Reddit, Twitter, or news aggregators), group together as one activity with a generic description.

### Do NOT split for

1. In-app transient UI (search, menus, settings), notifications, or auto-refresh.
2. Transition UI window managers, alt-tabbing etc.
3. Same domain family and topic (e.g., scrolling within one article/thread).


## Inactivity & Log Gaps

1. Short gaps in logs <= {{max_desktop_screenshot_log_interval_seconds}} may simply be due to the sampling frequency, not due to inactivity.
2. Longer gaps > {{max_desktop_screenshot_log_interval_seconds}} likely indicate inactivity.
  1. If there is an activity ongoing, it should be closed, with the close time being the timestamp of the last log before the gap plus 5 seconds.
3. If the user is inactive, do not create an activity for that period.
4. Things like screensaver, lock screen, or system idle time should not be represented as activities.

## Activity name and descriptions

1. As succinct as possible
2. Should include application name in name or description
3. Include title if relevant

{{ _.role("user") }}
Activity logs gathered over the last {{duration_seconds}} seconds:
{{ FormattedLogsList(logs) }}

{{ ctx.output_format }}
"#






function GenerateTimeline(
  logs: TimelineLog[],
  duration_seconds: int,
  max_pause_time_seconds: int,
  max_desktop_screenshot_log_interval_seconds: int
) -> TimelineWithReasoning {
  client "TextClient"

  prompt #"
    {{ TIMELINE_GENERATION_PROMPT(
      max_pause_time_seconds=max_pause_time_seconds ,
      logs=logs,
      duration_seconds=duration_seconds,
      max_desktop_screenshot_log_interval_seconds=max_desktop_screenshot_log_interval_seconds
    ) }}
  "#
}
