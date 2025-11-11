
// ---------- reusable text ----------
template_string TAGGING_RULES #"
You are an expert activity tagging analyst. Return the full set of tags that
faithfully characterize the activity. A tag is valid when the activity, as
described, is a clear and specific instance of the tag. The tags will be used by the user
in order to categorize and search their activities.

**Tag Assignment Guidelines**
- Accept tags supported by either explicit statements or strong logical
  implication. The connection must be obvious to a domain expert, not merely
  plausible.
- If multiple tags a are valid, return all of them.
- The connection to the activity must be clear and specific. For example,
  if the activity is "writing a report on climate change", the tags "writing", "climate change",
  and "report" are valid, but "communication" would be too vague.
- If no tag adequately matches, return an **empty list**.
- Return each chosen tag at most once.
- If tags are overlapping or hierarchical, you must return all that apply regardless of redundancy.

"#



// ---------- dynamic return class ----------

enum TagNames {
    @@dynamic
}



template_string FormatTags(tags: Tag[]) #"
{% for tag in tags %}

Name: {{ tag.name }}
Description: {{ tag.description }}
{% endfor %}

"#
class Tag {
    name        string
    description string
}
// TODO: Consider tagging activities in bulk to save on static prompt tokens
// ---------- main function ----------
function TagActivity(activity_name: string,
                     activity_description: string,
                     tag_catalog: Tag[]) -> TagNames[] {
  client "TextClient"            // choose a concrete client at call-time

  prompt #"
  {{ _.role("system") }}
  {{ TAGGING_RULES() }}

  {{ _.role("user") }}
  Available tags:
  {{ FormatTags(tag_catalog) }}

  Activity to tag:
  Name:
  {{ activity_name }}
  Description:
  {{ activity_description }}

  {{ ctx.output_format }}
  "#
                     }
test TestName {
  functions [TagActivity]
  args {
    activity_name #"
      hello world
    "#
    activity_description #"
      hello world
    "#
    tag_catalog [
      {
          name #"
          hello world
        "#
          description #"
          hello world
        "#
      },
      {
          name #"
          hello world
        "#
          description #"
          hello world
        "#
      }
    ]
  }
}
