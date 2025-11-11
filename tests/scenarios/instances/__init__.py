from .casual_web_browsing_and_social_media import (
    make_casual_web_browsing_and_social_media,
)
from .coding_then_afk import make_coding_then_afk
from .context_switching import make_context_switching
from .data_analysis_and_email import make_data_analysis_and_email
from .interrupted_content_creation import make_interrupted_content_creation
from .interrupted_design_work import make_interrupted_design_work
from .llm_stitching_match_writing import make_llm_stitching_match_writing
from .llm_stitching_no_match import make_llm_stitching_no_match
from .llm_stitching_required import make_llm_stitching_required
from .meeting_then_coding import make_meeting_then_coding
from .online_shopping_with_research import make_online_shopping_with_research
from .photo_editing_and_organization import make_photo_editing_and_organization
from .project_management_and_communication import (
    make_project_management_and_communication,
)
from .simple_coding import make_simple_coding_session


all_scenario_creation_funcs = [
    make_casual_web_browsing_and_social_media,
    make_simple_coding_session,
    make_coding_then_afk,
    make_context_switching,
    make_meeting_then_coding,
    make_online_shopping_with_research,
    make_photo_editing_and_organization,
    make_project_management_and_communication,
    make_interrupted_content_creation,
    make_interrupted_design_work,
    make_data_analysis_and_email,
    make_llm_stitching_required,
    make_llm_stitching_match_writing,
    make_llm_stitching_no_match,
]
