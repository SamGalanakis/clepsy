


class InterpretImageDesktopOCRInput {

    ocr_text string
    title string
    app_name string
}

template_string InterpretImageDesktopOCRExample #"
User is actively coding, debugging a project named "ProjectX".
"#


function InterpretImageDesktopOCR(input: InterpretImageDesktopOCRInput) -> string {
  client "TextClient"

  prompt #"
  {{ _.role("system") }}
  You are an expert at interpreting OCR text extracted from images, such as screenshots or photos. Your task is to analyze the provided OCR output along with contextual information about the image, and generate a concise and accurate description of the content depicted in the image.
  Specifically, you are dealing with screenshots from a users desktop computer, specifically a single window.
  We can not see the image, only the OCR text extracted from it as well as the title of the window and the application name.
  Your job is to interpret the text in the context of the provided title and application name, and produce a very concise summary.
  The summary should be targeted at information that may be useful for a time tracking application.

* Omit any personal or sensitive information.
* Prefer high-level phrasing (“watching a programming tutorial”) over exact titles.
* The description should be concise and dense. At most 20 words long, less is better.
* Do NOT include overly detailed information where it is not needed.
* If it is a browser, focus only on the shown tab.
* Do NOT make up any information that is not present in the OCR text or the title/app name.
* If the OCR text is garbled or nonsensical, focus on the title and app name to infer the activity.
* No need to mention the app name or title in the description, only use it to inform your understanding of the OCR text.


  {{ _.role("user") }}


  **Context:**
  - Title: "{{ input.title }}"
  - Application Name: "{{ input.app_name }}"
  **OCR Output:**
  "{{ input.ocr_text }}"
  "#
}
