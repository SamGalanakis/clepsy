import pytest

from baml_client.async_client import b
from baml_client.type_builder import TypeBuilder
import baml_client.types as baml_types
import clepsy.entities as E
from clepsy.llm import create_client_registry


pytestmark = pytest.mark.llm


TAG_CATALOG_DATA = [
    {
        "name": "Programming",
        "description": "Writing, debugging, or reviewing code in any programming language.",
    },
    {
        "name": "Meetings",
        "description": "Video calls, phone calls, or in-person meetings with colleagues or clients.",
    },
    {
        "name": "Communication",
        "description": "Email, messaging, or asynchronous communication with others.",
    },
    {
        "name": "Entertainment",
        "description": "Leisure activities like watching videos, playing games, or browsing for fun.",
    },
    {
        "name": "Social Media",
        "description": "Using social media platforms like Twitter, Instagram, Facebook, LinkedIn, etc.",
    },
    {
        "name": "Learning",
        "description": "Acquiring new knowledge through courses, tutorials, books, or documentation.",
    },
    {
        "name": "Education",
        "description": "Formal or informal educational activities including online courses and training.",
    },
    {
        "name": "Content Creation",
        "description": "Creating written content, videos, presentations, or other media.",
    },
    {
        "name": "Design",
        "description": "UI/UX design, graphic design, or working with design tools like Figma or Photoshop.",
    },
    {
        "name": "Collaboration",
        "description": "Working together with others on shared projects or tasks.",
    },
    {
        "name": "Administrative",
        "description": "Administrative tasks like filing paperwork, timesheets, or expense reports.",
    },
    {
        "name": "Reading",
        "description": "Reading articles, books, documentation, or other written content.",
    },
    {
        "name": "Data Science",
        "description": "Working with data analysis, machine learning, or statistics.",
    },
    {
        "name": "DevOps",
        "description": "Infrastructure, deployment, CI/CD, or system administration.",
    },
    {
        "name": "Testing",
        "description": "Writing or running tests, QA activities.",
    },
]


def build_type_builder(tag_catalog: list[baml_types.Tag]) -> TypeBuilder:
    tb = TypeBuilder()
    for tag in tag_catalog:
        tb.TagNames.add_value(tag.name)
    return tb


TEST_CASES = [
    (
        "API Bug Fix",
        "Updating the payments API endpoint to resolve a regression and rerunning the unit tests.",
        {"Programming", "Testing"},
    ),
    (
        "Sprint Planning Call",
        "Video conference with the engineering team to review tickets, assign owners, and confirm next steps.",
        {"Meetings", "Collaboration"},
    ),
    (
        "Support Inbox Triage",
        "Reading customer emails in Zendesk and drafting replies that resolve billing questions.",
        {"Communication", "Reading", "Content Creation"},
    ),
    (
        "Marketing Tweet Thread",
        "Publishing a promotional update thread on the company Twitter account.",
        {"Content Creation", "Social Media", "Communication"},
    ),
    (
        "Receipt Submission",
        "Uploading scanned receipts into the finance portal and categorizing each expense.",
        {"Administrative"},
    ),
    (
        "Netflix Break",
        "Watching a comedy special on Netflix for leisure.",
        {"Entertainment"},
    ),
    (
        "Design Feedback Session",
        "Reviewing new Figma mockups and documenting change requests for the design team in Slack.",
        {"Design", "Communication", "Collaboration", "Content Creation"},
    ),
    (
        "Computer Usage",
        "Using computer.",
        set(),
    ),
    (
        "Unit Test Implementation",
        "Adding pytest coverage for the authentication module and updating assertions.",
        {"Programming", "Testing"},
    ),
]


@pytest.mark.parametrize(
    "activity_name,activity_description,expected_tags",
    TEST_CASES,
)
async def test_tag_activity_classification(
    activity_name: str,
    activity_description: str,
    expected_tags: set[str],
    mock_llm_config: E.LLMConfig,
):
    """Ensure TagActivity returns exactly the tags that characterize the activity."""

    tag_catalog = [baml_types.Tag(**tag) for tag in TAG_CATALOG_DATA]

    client = create_client_registry(
        llm_config=mock_llm_config,
        name="TextClient",
        set_primary=True,
    )
    tb = build_type_builder(tag_catalog)

    result = await b.TagActivity(
        activity_name=activity_name,
        activity_description=activity_description,
        tag_catalog=tag_catalog,
        baml_options={"client_registry": client, "tb": tb},
    )

    actual_tags = set(result)

    assert actual_tags == expected_tags, (
        f"Tag mismatch for '{activity_name}':\n"
        f"Expected: {expected_tags}\n"
        f"Actual: {actual_tags}"
    )
