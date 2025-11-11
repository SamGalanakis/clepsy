



// baml_src/desktop_check_input_template.baml

template_string DesktopCheckInputTemplate(input: DesktopCheckInput) #"
- **Screenshot:** {{ input.screenshot }}
- **Active Window:**
- **Title:** {{ input.active_window.title }}
- **App Name:** {{ input.active_window.app_name }}
"#


function ValidateDesktopCheck(
  generated_description: string,
  expected_description: string,
  input: DesktopCheckInput
) -> ValidationResultWithReasoning {
  client "TestClient"

  prompt #"
  {{ _.role("system") }}
  You are an expert validator for desktop activity descriptions. Your task is to evaluate a generated description based on a screenshot and some context, and compare it against an expected description.

  **Instructions:**
  1.  Review the `HIGH_LEVEL_INSTRUCTIONS` that the original model was given.
  2.  Compare the `generated_description` with the `expected_description`.
  3.  Grade the result from 0.0 to 1.0. A grade of 0.5 or higher is considered passing.

  **Original Model Instructions (generation prompt):**
  {{ DESKTOP_CHECK_GENERATION_PROMPT(input) }}

  {{ _.role("user") }}
  **Input to the model:**
  {{ DesktopCheckInputTemplate(input) }}

  **Generated Description:**
  "{{ generated_description }}"

  **Expected Description:**
  "{{ expected_description }}"

  Please validate the generated description against the expected one, following the rules provided.
  Do not fail a model due to too many words as long as it is within 50% of the expected length.
  You must provide a grade and reasoning, your reasoning should be concise bullet points, as short and clear as possible.

  {{ ctx.output_format }}
  "#
}
