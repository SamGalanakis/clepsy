from datetime import timedelta
from typing import List

import baml_client.types as baml_types
import clepsy.entities as E

from ..types import TestScenario


def make_llm_stitching_required(base_time) -> TestScenario:
    """
    Test scenario that requires LLM-based stitching.

    The stitchable activity has name "Code Review" but the new activity
    has name "Reviewing Pull Requests" - similar semantically but different
    enough that programmatic stitching won't match (Levenshtein > 2).
    """
    input_logs: List[E.AggregationInputEvent] = [
        # 0:00 → 2:00: Code review activity
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time,
            active_window=E.WindowInfo(
                title="Pull Request #123 - GitHub",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User reviewing a pull request on GitHub.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(seconds=30),
            active_window=E.WindowInfo(
                title="Pull Request #123 - GitHub",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User reviewing code changes in a pull request.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=1),
            active_window=E.WindowInfo(
                title="Pull Request #123 - GitHub",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User examining code diff in pull request.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=1, seconds=30),
            active_window=E.WindowInfo(
                title="Pull Request #123 - GitHub",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User reviewing pull request changes.",
        ),
        # 2:00 → 5:00: Writing documentation
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=2),
            active_window=E.WindowInfo(
                title="README.md - VS Code",
                app_name="Visual Studio Code",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User writing documentation in markdown.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=2, seconds=30),
            active_window=E.WindowInfo(
                title="README.md - VS Code",
                app_name="Visual Studio Code",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User editing documentation file.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=3),
            active_window=E.WindowInfo(
                title="README.md - VS Code",
                app_name="Visual Studio Code",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User writing project documentation.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=3, seconds=30),
            active_window=E.WindowInfo(
                title="README.md - VS Code",
                app_name="Visual Studio Code",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User updating README documentation.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=4),
            active_window=E.WindowInfo(
                title="README.md - VS Code",
                app_name="Visual Studio Code",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User writing documentation content.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=4, seconds=30),
            active_window=E.WindowInfo(
                title="README.md - VS Code",
                app_name="Visual Studio Code",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User editing documentation.",
        ),
        # 5:00 → 10:00: More documentation work to fill the 10-minute window
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=5),
            active_window=E.WindowInfo(
                title="README.md - VS Code",
                app_name="Visual Studio Code",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User writing documentation.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=6),
            active_window=E.WindowInfo(
                title="README.md - VS Code",
                app_name="Visual Studio Code",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User updating documentation.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=7),
            active_window=E.WindowInfo(
                title="README.md - VS Code",
                app_name="Visual Studio Code",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User editing documentation file.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=8),
            active_window=E.WindowInfo(
                title="README.md - VS Code",
                app_name="Visual Studio Code",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User writing project documentation.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=9),
            active_window=E.WindowInfo(
                title="README.md - VS Code",
                app_name="Visual Studio Code",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User editing documentation content.",
        ),
    ]

    # Previous activity that should be stitched with the new code review activity
    # Note: "Code Review" vs "Reviewing Pull Requests" - semantically similar but
    # Levenshtein distance of normalized strings is > 2
    stitchable_closed_activities = [
        E.DBActivityWithLatestEvent(
            activity=E.DBActivity(
                id=1,
                name="Code Review",
                description="Reviewing code changes in GitHub pull requests.",
                productivity_level=E.ProductivityLevel.PRODUCTIVE,
                last_manual_action_time=None,
                source=E.Source.AUTO,
            ),
            latest_event=E.DBActivityEvent(
                id=1,
                event_time=base_time - timedelta(minutes=1),
                event_type=E.ActivityEventType.CLOSE,
                aggregation_id=1,
                activity_id=1,
                last_manual_action_time=None,
            ),
            latest_aggregation=E.DBAggregation(
                start_time=base_time - timedelta(minutes=11),
                end_time=base_time - timedelta(minutes=1),
                first_timestamp=base_time - timedelta(minutes=11),
                last_timestamp=base_time - timedelta(minutes=1),
                id=1,
            ),
        )
    ]

    # Generated timeline activities with different naming
    generated_timeline_activities = {
        "llm_pr_review": baml_types.ActivityMetadata(
            name="Reviewing Pull Requests",
            description="Examining and providing feedback on code changes in GitHub.",
        ),
        "llm_docs": baml_types.ActivityMetadata(
            name="Documentation Writing",
            description="Creating and updating project documentation.",
        ),
    }

    generated_timeline_events = [
        baml_types.Event(
            t="0m0s",
            event_type="open",
            activity_id="llm_pr_review",
        ),
        baml_types.Event(
            t="2m0s",
            event_type="close",
            activity_id="llm_pr_review",
        ),
        baml_types.Event(
            t="2m0s",
            event_type="open",
            activity_id="llm_docs",
        ),
        baml_types.Event(
            t="10m0s",
            event_type="close",
            activity_id="llm_docs",
        ),
    ]

    # New activities (not stitched)
    new_activities = {
        "llm_docs": baml_types.ActivityMetadata(
            name="Documentation Writing",
            description="Creating and updating project documentation.",
        ),
    }

    # Events for new activities
    new_activity_events = [
        baml_types.Event(
            t="2m0s",
            event_type="open",
            activity_id="llm_docs",
        ),
        baml_types.Event(
            t="10m0s",
            event_type="close",
            activity_id="llm_docs",
        ),
    ]

    # Events for stitched activities
    stitched_activities_events = [
        # The existing "Code Review" activity gets stitched with new PR review activity
        E.NewActivityEventExistingActivity(
            event_time=base_time,
            event_type=E.ActivityEventType.OPEN,
            activity_id=1,
        ),
        E.NewActivityEventExistingActivity(
            event_time=base_time + timedelta(minutes=2),
            event_type=E.ActivityEventType.CLOSE,
            activity_id=1,
        ),
    ]

    # Expected output: Code Review should be stitched with Reviewing Pull Requests
    # using LLM (programmatic matching won't catch this)
    expected_aggregator_output = E.AggregatorCoreOutput(
        new_activities=new_activities,
        new_activity_events=new_activity_events,
        stitched_activities_events=stitched_activities_events,
        unstitched_activities_close_events=[],
        activities_to_update=[
            # LLM should merge the names/descriptions
            (
                1,
                {
                    "name": "Code Review",  # LLM should provide merged name
                    "description": "Reviewing code changes in GitHub pull requests.",
                },
            ),
        ],
    )

    aggregation_time_span = E.TimeSpan(
        start_time=base_time,
        end_time=base_time + timedelta(minutes=10),
    )

    return TestScenario(
        name="llm_stitching_required",
        description=(
            "Tests LLM-based stitching where programmatic matching fails. "
            "'Code Review' should be stitched with 'Reviewing Pull Requests' "
            "based on semantic similarity, not string distance."
        ),
        input_logs=input_logs,
        generated_timeline_activities=generated_timeline_activities,
        generated_timeline_events=generated_timeline_events,
        expected_aggregator_output=expected_aggregator_output,
        stitchable_activity_to_llm_id={1: "llm_pr_review"},
        aggregation_time_span=aggregation_time_span,
        previous_aggregation_end_time=base_time - timedelta(minutes=1),
        stitchable_closed_activities=stitchable_closed_activities,
        open_auto_activities=[],
    )
