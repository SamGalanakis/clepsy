
class ValidationResult {
  error_description string?
    @description("If invalid, explain the key errors; null when valid.")
  grade float
    @description("0.0 – 1.0 quality score; > 0.5 is a pass.")
}

class ValidationResultWithReasoning {
  reasoning string
    @description("Step-by-step explanation of checks and findings.")
  validation_result ValidationResult
    @description("Final verdict.")
}

// ───────────────────────────────────────────────
//  Validation Rules Template
// ───────────────────────────────────────────────
template_string TIMELINE_VALIDATION_RULES(max_pause_time_seconds:int) #"
**Timeline Validation Rules**

1. **Temporal Consistency**
   - First event for each activity is `open`.
   - Events strictly alternate `open` → `close` → `open` … .
   - No events after a definitive `close` for the same activity.
   - Events for each activity are time-ascending.

2. **Grace-Time Logic** ({{ max_pause_time_seconds }} seconds)
   - A `close` is *final* if no `open` follows **and** {{ max_pause_time_seconds }} seconds have passed.
   - A `close` inside the grace window may be followed by a resume (`open`).

3. **Logical Consistency**
   - Names / descriptions make sense for the summary.
   - No impossible rapid switches or overlapping tasks.
   - Durations are plausible.

4. **Input-Output Alignment**
   - Activities reflect the desktop-check summary.
   - Timeline spans the aggregation window.

5. **Structural Integrity**
   - Top-level keys `events` (array, may be empty) and `activities` (object) **must exist**.
   - Every `event.activity_id` appears as a unique key in `activities`.
   - Event timestamps lie inside the aggregation span.

6. **Leniency for Minor Variations**
   - Small time drifts (± a few seconds) or wording tweaks are OK.
   - Note deviations in reasoning even when still passing.

7. **Grading**
   - 0.9–1.0 Excellent · 0.7–0.8 Good · 0.5–0.6 Minimum pass · 0.3–0.4 Poor · < 0.3 Fail.
"#

class OpenAutoActivity {
  llm_id  string
    @description("LLM-assigned ID.")
  last_event Event
  @description(#"
  Last event for this auto activity, which is still open.
  "#)
  name string
    @description("Name of the open auto activity.")
  description string
    @description("Description of the open auto activity.")
}


template_string FormatGeneratedTimeline(
  generated_activities: map<string, ActivityMetadata>,
  generated_events: Event[],
) #"
  {
    "activities": {
      {%- for activity_id, activity in generated_activities | items %}
      "{{ activity_id }}": {
        "name": "{{ activity.name }}",
        "description": "{{ activity.description }}",
      }{%- if not loop.last %},{% endif %}
      {%- endfor %}
    },
    "events": [
      {%- for event in generated_events %}
      {
        "activity_id": "{{ event.activity_id }}",
        "t": "{{ event.t }}",
        "type": "{{ event.event_type }}",
      }{%- if not loop.last %},{% endif %}
      {%- endfor %}
    ]
  }
  "#










function ValidateTimelineAgainstExpected(
  generated_activities: map<string, ActivityMetadata>,
  generated_events: Event[],
  expected_generated_activities: map<string, ActivityMetadata>,
  expected_generated_events: Event[],
  duration_seconds: int,
  max_pause_time_seconds: int,
  max_desktop_screenshot_log_interval_seconds: int,
  input_logs: TimelineLog[],
) -> ValidationResultWithReasoning {
  client "TextClient"

  prompt #"
{{ _.role("system") }}
You are an expert timeline validator. Assess the generated timeline against
the rules and context that guided the aggregator LLM.

{{ TIMELINE_VALIDATION_RULES(max_pause_time_seconds) }}

──────────────── Aggregator Prompt (context) ────────────────
{{ TIMELINE_GENERATION_PROMPT(
       max_pause_time_seconds=max_pause_time_seconds ,
      logs=input_logs,
      duration_seconds=duration_seconds,
      max_desktop_screenshot_log_interval_seconds=max_desktop_screenshot_log_interval_seconds
) }}

──────────────── Formatted Generated Timeline ────────────────
{{ FormatGeneratedTimeline(
    generated_activities=generated_activities,
    generated_events=generated_events
) }}
```

──────────────── Formatted Expected Timeline ────────────────
{{ FormatGeneratedTimeline(
    generated_activities=expected_generated_activities,
    generated_events=expected_generated_events
) }}

The generated timeline should roughly match this reference;
minor, reasonable deviations are acceptable.

**Validation Steps**
1. Check structural integrity and field presence.
2. Verify temporal & grace-time logic.
3. Cross-check alignment with the summary.
4. Note any rule violations or deviations.
5. Assign a grade 0.0 – 1.0 (0.5 is the minimum passing grade).
6. Summarise key errors, especially for non-passing grades.

{{ ctx.output_format }}
"#
}
