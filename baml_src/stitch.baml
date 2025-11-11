
class ActivityStitchingInput {
    name string
    description string
}


class ActivityStitchOutput {
    name string
    description string
}


template_string FormatActivityStitchingInput(
    activity: ActivityStitchingInput,
    ) #"
Name: {{ activity.name }}
Description: {{ activity.description }}
"#


template_string TO_STITCH_RULES() #"
**Activities should be considered distinct or not according to the following rules / examples**
1. Activity pertains to different tasks like gaming vs coding.
2. Activity has different contexts, e.g., work vs leisure.
3. If they are both coding but are within the same project, they are considered a continuation.
4. If they are both coding but are in different projects, they are considered distinct.
"#

template_string TO_STITCH_PROMPT(
  activity_a_input: ActivityStitchingInput,
  activity_b_input: ActivityStitchingInput,
) #"
{{ _.role("system") }}
You are an expert on timeline creation and activity stitching. Your task is to decide if activity_a is a continuation of activity_b or should be considered a distinct activity.
Return true if they are a continuation, false if they are distinct.

{{ TO_STITCH_RULES() }}
{{ _.role("user") }}
Activity A:
{{ FormatActivityStitchingInput(activity_a_input) }}
Activity B:
{{ FormatActivityStitchingInput(activity_b_input) }}

Please provide your reasoning and then return a boolean value in the following format:
{{ ctx.output_format }}
"#



// Combined function: decides if activities should be stitched AND returns merged result
// Returns null if activities should NOT be stitched
template_string STITCH_OR_SKIP_PROMPT(
  activity_a: ActivityStitchingInput,
  activity_b: ActivityStitchingInput,
) #"
{{ _.role("system") }}
You are an expert on timeline creation and activity stitching. Your task is to:
1. Decide if activity_a is a continuation of activity_b or if they are distinct activities
2. If they ARE a continuation, create a joint name and description for them
3. If they are NOT a continuation, return null

**Activities should be considered distinct according to these rules:**
1. Activity pertains to different tasks like gaming vs coding
2. Activity has different contexts, e.g., work vs leisure
3. If they are both coding but in different projects, they are distinct
4. If they are both coding in the same project, they are a continuation

**If stitching:** Combine the names and descriptions into a single coherent name and description.
The joint name should be concise and descriptive. You may reuse the original text if no changes are needed.

{{ _.role("user") }}
Activity A:
{{ FormatActivityStitchingInput(activity_a) }}
Activity B:
{{ FormatActivityStitchingInput(activity_b) }}

Return the joint activity (with name and description) if they should be stitched, or null if they should remain distinct.

{{ ctx.output_format }}
"#

function StitchOrSkip(
  activity_a: ActivityStitchingInput,
  activity_b: ActivityStitchingInput,
) -> ActivityStitchOutput | null {
  client "TextClient"

  prompt #"{{STITCH_OR_SKIP_PROMPT(
      activity_a,
      activity_b
    )}}"#
}
