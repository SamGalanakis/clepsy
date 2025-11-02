// TODO: Worth making this a bulk activity classifier? So as to only pay static input token cost once

function ClassifyActivityProductivity(activity_name:string,activity_description:string ,productivity_guidelines:string) -> ProductivityLevel {
client "TextClient"
prompt #"
    {{ _.role("system") }}
    You are an expert in productivity level classification.
    Your task is to classify the productivity level of the given activity based on its description.
    Please classify the productivity level of the activity based on the following guidelines:
    {{ productivity_guidelines }}

    {{ _.role("user") }}
    This is the activity to classify:
    Activity Name: {{ activity_name}}
    Activity Description: {{ activity_description}}
     {{ ctx.output_format }}
    "#

}

test name {
    functions [ClassifyActivityProductivity]
    args {
        activity_name "Reading"
        activity_description "Reading a book on productivity techniques."
        productivity_guidelines "**VERY_PRODUCTIVE (Deep Focus Work)** - Core deliverables that directly create value (writing, coding, designing) - Complex problem-solving and strategic planning requiring full concentration - Examples: Writing research papers, focused coding sessions, architectural design **PRODUCTIVE** - Supporting work that enables deep tasks (code reviews, structured meetings) - Knowledge acquisition essential to ongoing projects - Examples: Reading technical docs, sprint planning, project meetings **NEUTRAL** - Routine communication and coordination - Administrative tasks and brief check-ins - Examples: Email triage, team chat, scheduling **DISTRACTING** - Frequent context-switching activities - Non-essential browsing or casual social interactions - Examples: Social media scrolling, random web reading, unstructured chat **VERY_DISTRACTING** - Activities that actively pull focus away from work - Entertainment during work hours or unrelated content consumption - Examples: Gaming, entertainment videos, personal social feeds **Classification Guidelines:** 1. Consider the user’s role and current priorities. 2. Judge by the content of the activity, not just the tool used. 3. Account for duration and continuity of focus."

    }
}
