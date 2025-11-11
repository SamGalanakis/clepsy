

class SessionIdentifier {
    session_id string @description("Should be a short descriptive lower-snake-case slug")
    title string @description("Title of the session, should be short human-readable text, to be shown in users calendar.")
}


class SessionActivityMetadata {
  name        string
  description string
  activity_id string
  duration   string
  @description("Description of the activity.")
}

enum ActivityIds {
    @@dynamic
}



class SessionOutput {
  session SessionIdentifier
  activity_ids ActivityIds[] @description(#"
List of activity IDs that are part of this session. Each entry should corresdpond exactly to an activity_id from the input activities.
They will be lowercase descriptive slugs e.g. 'checking_email' NOT numeric IDs.
  "#)
}

template_string EXTRACT_SESSIONS_PROMPT(
  activities: SessionActivityMetadata[],
    tags: Tag[],
    preexisting_sessions: SessionIdentifier[]
) #"
    {{ _.role("system") }}
    You are a timeline analysis expert. Your task is to identify and group related activities into sessions based on their descriptions, names and tags.
    A session is defined as a series of related activities that together represent a coherent block of work or focus.
    A session can be related to a common project, task, or theme. You should create at most 5 session identifiers, each with a unique session_id and a descriptive title.
    Sessions will be used to group activities in a calendar view, so the title should be concise and informative.
    Each session should include a list of activity IDs that are part of that session. An activity can belong to 0 or more sessions (these are candidate sessions).
    Only include sessions that are plausible given the activity data, you may return less than 5 sessions or no sessions at all if the activity data does not support it.
    Favor creating sessions that apply to longer total duration, whether through longer individual activities or more activities in total.
    Favor sessions that are distinct from each other, avoid creating sessions that are very similar or overlapping in focus.
    Sessions should include at least 2 activities to be considered valid.

    Some examples of session titles:
    - "Project Alpha Development"
    - "Marketing Strategy Meeting"
    - "Client AlphaFarma Onboarding"
    - "Browsing Political News Sites"
    - "Researching Transformer Architecture"
    - "Clearning up Email Inbox"
    - "Scrolling Instagram"
    - "Laptop Review Videos"


    {% if preexisting_sessions %}
    # Pre-existing sessions
    Pre-existing sessions have been provided, you should reuse these if they are relevant to the activities. You may directly use the session_id in the output, no need to recreate them.
    Allways include pre-existing sessions in the output, if they are relevant to at least one activity. These do not count towards the maximum of 5 sessions you should create.
    New sessions you create should not be duplicates of the pre-existing sessions, they need to be distinct.

    Pre-existing sessions:
    {% for session in preexisting_sessions %}
    - ID: {{ session.session_id }} – Title: {{ session.title }}
    {% endfor %}
    {% endif %}


    {% if tags | length > 0 %}
    # Available tags
    The following user created tags are available and may be useful in identifying sessions that the user may be interested in.
    Use these where appropriate to help identify sessions, but do not feel constrained to only using these.
    Available tags (name – description):
    {% for tag in tags %}
    - {{ tag.name }} – {{ tag.description }}
    {% endfor %}
    {% endif %}

    {{_.role("user") }}

    Here is a list of activities with their metadata. Use this information to identify and group related activities into sessions.
    The activities are in chronological order, use that as a hint regarding which activities may form sessions together.
    Activities:
    {% for activity in activities %}
    - Name: {{ activity.name }}
      Activity ID: {{ activity.activity_id }}
      Description: {{ activity.description }}
      Duration: {{ activity.duration }}

    {% endfor %}

    Respond strictly in the following format:
    {{ ctx.output_format }}
"#

function ExtractSessions(
  activities: SessionActivityMetadata[],
  tags: Tag[],
  preexisting_sessions: SessionIdentifier[]
) -> SessionOutput[] {
  client "TextClient"

  prompt #"{{EXTRACT_SESSIONS_PROMPT(
    activities=activities,
    tags=tags,
    preexisting_sessions=preexisting_sessions


  )}}"#
}
