// baml_src/timeline_fix.baml


class FixedTimelineWithReasoning {
  reasoning string @description(#"
Step-by-step explanation of the changes made to the timeline, or 'no changes' if no corrections were needed.
  "#)
  timeline (Timeline | "no changes") @description(#"
The fixed timeline, or 'no changes' if no corrections were needed.")
  "#)
}

function QualityControlTimeline(
  generated_timeline: Timeline,
  logs: TimelineLog[],
  duration_seconds: int,
  max_pause_time_seconds: int,
  errors: string[]?
) -> FixedTimelineWithReasoning {
  client "TextClient"

  prompt #"
{{ _.role("system") }}
You are an expert timeline quality controler. Your task is to review a generated timeline, identify any inconsistencies or errors based on the provided rules and context, and output a corrected timeline.


──────────────── Aggregator Prompt (context) ────────────────
This was the prompt used to generate the timeline you are fixing.
{{ TIMELINE_GENERATION_PROMPT(
      duration_seconds=duration_seconds,
      logs=logs,
      max_pause_time_seconds=max_pause_time_seconds,
      max_desktop_screenshot_log_interval_seconds=max_pause_time_seconds
) }}

──────────────── Timeline to Inspect ────────────────
{{ generated_timeline }}

{% if errors %}
──────────────── Programmatic Validation Errors ────────────────
The following errors were found by a programmatic check. You must fix these errors in addition to any other issues you find in the timeline.
{% for error in errors %}
- {{ error }}
{% endfor %}
{% endif %}

**Your Task**
1.  **Review:** Carefully examine the timeline against the rules and the original summary.
2.  **Fix:** Correct any structural, logical, or temporal errors. This might involve adding, removing, or modifying events and activities.
3.  **Reasoning:** Explain the changes you made and why. If no changes are needed, state that clearly.
4.  **Output:**
    - If you made corrections, provide the complete, fixed `Timeline`.
    - If the original timeline is already perfect, output the string "no changes" for the `timeline` field instead.

{{ ctx.output_format }}
"#
}
