



// ---------- Window & desktop ----------
class WindowInfo {
  title        string
  app_name     string
  is_active    bool
}








class DesktopCheckInput {
  screenshot  image
    @description("Raw screenshot; will be automatically resized on the server side before the prompt is built.")
  active_window WindowInfo
    @description("Foreground window at capture time, if known.")
}





template_string EXAMPLE #"
User is actively coding in VS Code, debugging a project named "ProjectX".
"#

// Reusable full prompt template for desktop check generation
template_string DESKTOP_CHECK_GENERATION_PROMPT(input: DesktopCheckInput) #"
{{ _.role("system") }}
You are an expert in time management and have been enlisted by the user to log their
desktop activities so they can analise their work patterns. The user will provide you with
a screenshot of a window, along with the title and application name.


* Omit any personal or sensitive information.
* Prefer high-level phrasing (“watching a programming tutorial”) over exact titles.
* The description should be concise and dense. At most 20 words long, less is better.
* Do NOT include overly detailed information where it is not needed.
* If it is a browser, focus only on the shown tab.
{{ _.role("user") }}


Please describe what you see at a high level in the screenshot provided.
The screenshot is of a single application window, on a desktop environment.
The followng information is available:

- **Screenshot:**  {{ input.screenshot }}
- **Window Title:** `{{ input.active_window.title }}`
- **App Name:** `{{ input.active_window.app_name }}`

Here is an example of the level of detail you should provide:
{{ EXAMPLE() }}
"#

// ---------- Main function ----------
function DescribeDesktopScreenshot(input: DesktopCheckInput) -> string {
  client "ImageClient"

  prompt #"
  {{ DESKTOP_CHECK_GENERATION_PROMPT(input) }}
  "#
}



test TestName {
  functions [DescribeDesktopScreenshot]
  args {
    input {
        screenshot { file "/app/test_images/Adobe-Photoshop-Screenshot.png" }
        active_window {
          title #"
          hello world
        "#
          app_name #"
          hello world
        "#
          is_active true
      }
    }
  }
}
