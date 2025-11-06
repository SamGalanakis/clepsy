from datetime import timedelta
from typing import List
from uuid import uuid4

import baml_client.types as baml_types
from clepsy import utils
import clepsy.entities as E
from clepsy.entities import AggregatorCoreOutput

from ..types import ManualReconciliationCase, TestScenario


def make_meeting_then_coding(base_time) -> TestScenario:
    STATIC_ID = uuid4()
    # Screenshot cadence: 30s within app, 5s at switches (Zoom → Slack at 5:00, Slack → VSCode at 10:00)
    input_logs: List[E.AggregationInputEvent] = [
        # Zoom standup (0:00 → 4:55)
        E.ProcessedDesktopCheckScreenshotEventVLM(
            id=STATIC_ID,
            timestamp=base_time + timedelta(seconds=0),
            active_window=E.WindowInfo(
                title="Daily Standup - Zoom Meeting",
                app_name="Zoom",
                bbox=E.Bbox(left=200, top=100, width=1000, height=700),
            ),
            llm_description="Joining the daily standup meeting in Zoom.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            id=STATIC_ID,
            timestamp=base_time + timedelta(seconds=30),
            active_window=E.WindowInfo(
                title="Daily Standup - Zoom Meeting",
                app_name="Zoom",
                bbox=E.Bbox(left=200, top=100, width=1000, height=700),
            ),
            llm_description="In Zoom standup discussing updates.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            id=STATIC_ID,
            timestamp=base_time + timedelta(minutes=1, seconds=0),
            active_window=E.WindowInfo(
                title="Daily Standup - Zoom Meeting",
                app_name="Zoom",
                bbox=E.Bbox(left=200, top=100, width=1000, height=700),
            ),
            llm_description="Ongoing Zoom standup.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            id=STATIC_ID,
            timestamp=base_time + timedelta(minutes=4, seconds=55),
            active_window=E.WindowInfo(
                title="Daily Standup - Zoom Meeting",
                app_name="Zoom",
                bbox=E.Bbox(left=200, top=100, width=1000, height=700),
            ),
            llm_description="Wrapping up Zoom standup.",
        ),
        # Slack follow-up (5:00 → 9:55)
        E.ProcessedDesktopCheckScreenshotEventVLM(
            id=STATIC_ID,
            timestamp=base_time + timedelta(minutes=5, seconds=0),
            active_window=E.WindowInfo(
                title="team-chat - Slack",
                app_name="Slack",
                bbox=E.Bbox(left=300, top=200, width=800, height=600),
            ),
            llm_description="Post-meeting discussion in Slack (team-chat).",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            id=STATIC_ID,
            timestamp=base_time + timedelta(minutes=5, seconds=30),
            active_window=E.WindowInfo(
                title="team-chat - Slack",
                app_name="Slack",
                bbox=E.Bbox(left=300, top=200, width=800, height=600),
            ),
            llm_description="Clarifying action items in Slack.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            id=STATIC_ID,
            timestamp=base_time + timedelta(minutes=9, seconds=55),
            active_window=E.WindowInfo(
                title="team-chat - Slack",
                app_name="Slack",
                bbox=E.Bbox(left=300, top=200, width=800, height=600),
            ),
            llm_description="Sharing links in Slack post-standup.",
        ),
        # Coding in VSCode (10:00)
        E.ProcessedDesktopCheckScreenshotEventVLM(
            id=STATIC_ID,
            timestamp=base_time + timedelta(minutes=10, seconds=0),
            active_window=E.WindowInfo(
                title="feature.py - Visual Studio Code",
                app_name="Visual Studio Code",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Starting feature development in VS Code (feature.py).",
        ),
    ]

    activities = {
        "standup_meeting": baml_types.ActivityMetadata(
            name="Daily Standup Meeting",
            description="Team standup meeting on Zoom",
        ),
        "post_meeting_chat": baml_types.ActivityMetadata(
            name="Team Communication",
            description="Follow-up discussion in Slack after standup",
        ),
        "feature_development": baml_types.ActivityMetadata(
            name="Feature Development",
            description="Implementing new feature in Python",
        ),
    }

    events = [
        baml_types.Event(
            activity_id="standup_meeting",
            event_type="open",
            t="0m0s",
        ),
        baml_types.Event(
            activity_id="standup_meeting",
            event_type="close",
            t="5m0s",
        ),
        baml_types.Event(
            activity_id="post_meeting_chat",
            event_type="open",
            t="5m0s",
        ),
        baml_types.Event(
            activity_id="post_meeting_chat",
            event_type="close",
            t="10m0s",
        ),
        baml_types.Event(
            activity_id="feature_development",
            event_type="open",
            t="10m0s",
        ),
    ]
    events.sort(key=lambda x: utils.mm_ss_to_timedelta(x.t))

    expected_aggregator_output = AggregatorCoreOutput(
        new_activities=activities,
        new_activity_events=events,
        stitched_activities_events=[],
        unstitched_activities_close_events=[],
        activities_to_update=[],
    )

    aggregation_time_span = E.TimeSpan(
        start_time=base_time, end_time=base_time + timedelta(minutes=10)
    )
    # Manual specs for various cases
    # Non-overlap manual activity
    manual_non_overlap_activity = E.DBActivity(
        id=6201,
        name="Personal Task",
        description="Manual personal activity",
        productivity_level=E.ProductivityLevel.NEUTRAL,
        last_manual_action_time=None,
        source=E.Source.MANUAL,
    )
    manual_non_overlap_events = [
        E.DBActivityEvent(
            id=31,
            event_time=base_time - timedelta(minutes=30),
            event_type=E.ActivityEventType.OPEN,
            aggregation_id=None,
            activity_id=manual_non_overlap_activity.id,
            last_manual_action_time=None,
        ),
        E.DBActivityEvent(
            id=32,
            event_time=base_time - timedelta(minutes=25),
            event_type=E.ActivityEventType.CLOSE,
            aggregation_id=None,
            activity_id=manual_non_overlap_activity.id,
            last_manual_action_time=None,
        ),
    ]
    manual_non_overlap_specs = [
        E.DBActivitySpec(
            activity=manual_non_overlap_activity, events=manual_non_overlap_events
        )
    ]

    # Mixed overlap:
    # - One manual overlaps 'Daily Standup Meeting' with exact name -> remove that auto
    # - Another manual overlaps 'Team Communication' but is unrelated -> do not remove
    manual_overlap_match_activity = E.DBActivity(
        id=6202,
        name="Daily Standup Meeting",
        description="Team standup meeting on Zoom",
        productivity_level=E.ProductivityLevel.NEUTRAL,
        last_manual_action_time=None,
        source=E.Source.MANUAL,
    )
    manual_overlap_match_events = [
        E.DBActivityEvent(
            id=33,
            event_time=base_time + timedelta(minutes=0),
            event_type=E.ActivityEventType.OPEN,
            aggregation_id=None,
            activity_id=manual_overlap_match_activity.id,
            last_manual_action_time=None,
        ),
        E.DBActivityEvent(
            id=34,
            event_time=base_time + timedelta(minutes=4),
            event_type=E.ActivityEventType.CLOSE,
            aggregation_id=None,
            activity_id=manual_overlap_match_activity.id,
            last_manual_action_time=None,
        ),
    ]
    manual_overlap_no_match_activity = E.DBActivity(
        id=6203,
        name="Household Chore",
        description="Unrelated manual activity",
        productivity_level=E.ProductivityLevel.NEUTRAL,
        last_manual_action_time=None,
        source=E.Source.MANUAL,
    )
    manual_overlap_no_match_events = [
        E.DBActivityEvent(
            id=35,
            event_time=base_time + timedelta(minutes=6),
            event_type=E.ActivityEventType.OPEN,
            aggregation_id=None,
            activity_id=manual_overlap_no_match_activity.id,
            last_manual_action_time=None,
        ),
        E.DBActivityEvent(
            id=36,
            event_time=base_time + timedelta(minutes=9),
            event_type=E.ActivityEventType.CLOSE,
            aggregation_id=None,
            activity_id=manual_overlap_no_match_activity.id,
            last_manual_action_time=None,
        ),
    ]
    manual_mixed_specs = [
        E.DBActivitySpec(
            activity=manual_overlap_match_activity, events=manual_overlap_match_events
        ),
        E.DBActivitySpec(
            activity=manual_overlap_no_match_activity,
            events=manual_overlap_no_match_events,
        ),
    ]

    return TestScenario(
        name="meeting_then_coding",
        input_logs=input_logs,
        generated_timeline_activities=activities,
        generated_timeline_events=events,
        expected_aggregator_output=expected_aggregator_output,
        stitchable_activity_to_llm_id={},
        description="Meeting followed by Slack follow-up and coding, with frequent screenshots",
        aggregation_time_span=aggregation_time_span,
        previous_aggregation_end_time=aggregation_time_span.start_time,
        manual_reconciliation_cases=[
            ManualReconciliationCase(
                name="non_overlap",
                manual_activity_specs=manual_non_overlap_specs,
                expected_after_manual_activities=activities,
                expected_after_manual_events=events,
            ),
            ManualReconciliationCase(
                name="mixed_overlap",
                manual_activity_specs=manual_mixed_specs,
                expected_after_manual_activities={
                    # 'standup_meeting' removed due to exact name match, others remain
                    "post_meeting_chat": baml_types.ActivityMetadata(
                        name="Team Communication",
                        description="Follow-up discussion in Slack after standup",
                    ),
                    "feature_development": baml_types.ActivityMetadata(
                        name="Feature Development",
                        description="Implementing new feature in Python",
                    ),
                },
                expected_after_manual_events=[
                    baml_types.Event(
                        activity_id="post_meeting_chat",
                        event_type="open",
                        t="5m0s",
                    ),
                    baml_types.Event(
                        activity_id="post_meeting_chat",
                        event_type="close",
                        t="10m0s",
                    ),
                    baml_types.Event(
                        activity_id="feature_development",
                        event_type="open",
                        t="10m0s",
                    ),
                ],
            ),
            # Ambiguous overlap that shares tokens with 'Team Communication' but not exact
            ManualReconciliationCase(
                name="llm_overlap_ambiguous",
                manual_activity_specs=[
                    E.DBActivitySpec(
                        activity=E.DBActivity(
                            id=6204,
                            name="Team Comms",
                            description="Similar to Team Communication",
                            productivity_level=E.ProductivityLevel.NEUTRAL,
                            last_manual_action_time=None,
                            source=E.Source.MANUAL,
                        ),
                        events=[
                            E.DBActivityEvent(
                                id=37,
                                event_time=base_time + timedelta(minutes=5),
                                event_type=E.ActivityEventType.OPEN,
                                aggregation_id=None,
                                activity_id=6204,
                                last_manual_action_time=None,
                            ),
                            E.DBActivityEvent(
                                id=38,
                                event_time=base_time + timedelta(minutes=9),
                                event_type=E.ActivityEventType.CLOSE,
                                aggregation_id=None,
                                activity_id=6204,
                                last_manual_action_time=None,
                            ),
                        ],
                    )
                ],
                expected_after_manual_activities={
                    # Remove 'post_meeting_chat' due to ambiguous but implausible multitasking
                    "standup_meeting": baml_types.ActivityMetadata(
                        name="Daily Standup Meeting",
                        description="Team standup meeting on Zoom",
                    ),
                    "feature_development": baml_types.ActivityMetadata(
                        name="Feature Development",
                        description="Implementing new feature in Python",
                    ),
                },
                expected_after_manual_events=[
                    baml_types.Event(
                        activity_id="standup_meeting",
                        event_type="open",
                        t="0m0s",
                    ),
                    baml_types.Event(
                        activity_id="standup_meeting",
                        event_type="close",
                        t="5m0s",
                    ),
                    baml_types.Event(
                        activity_id="feature_development",
                        event_type="open",
                        t="10m0s",
                    ),
                ],
            ),
            # Mixed: one exact match (remove) + one ambiguous (LLM) + one disjoint (keep)
            ManualReconciliationCase(
                name="llm_mixed_overlap",
                manual_activity_specs=[
                    # Exact match to remove standup
                    E.DBActivitySpec(
                        activity=manual_overlap_match_activity,
                        events=manual_overlap_match_events,
                    ),
                    # Ambiguous similar to Team Communication
                    E.DBActivitySpec(
                        activity=E.DBActivity(
                            id=6205,
                            name="Communication Team",
                            description="Similar to Team Communication",
                            productivity_level=E.ProductivityLevel.NEUTRAL,
                            last_manual_action_time=None,
                            source=E.Source.MANUAL,
                        ),
                        events=[
                            E.DBActivityEvent(
                                id=39,
                                event_time=base_time + timedelta(minutes=5),
                                event_type=E.ActivityEventType.OPEN,
                                aggregation_id=None,
                                activity_id=6205,
                                last_manual_action_time=None,
                            ),
                            E.DBActivityEvent(
                                id=40,
                                event_time=base_time + timedelta(minutes=9),
                                event_type=E.ActivityEventType.CLOSE,
                                aggregation_id=None,
                                activity_id=6205,
                                last_manual_action_time=None,
                            ),
                        ],
                    ),
                    # Disjoint overlapping 'Household Chore' (keep)
                    E.DBActivitySpec(
                        activity=manual_overlap_no_match_activity,
                        events=manual_overlap_no_match_events,
                    ),
                ],
                expected_after_manual_activities={
                    # Standup removed (exact), 'post_meeting_chat' also removed due to ambiguous overlap; feature dev remains
                    "feature_development": baml_types.ActivityMetadata(
                        name="Feature Development",
                        description="Implementing new feature in Python",
                    ),
                },
                expected_after_manual_events=[
                    baml_types.Event(
                        activity_id="feature_development",
                        event_type="open",
                        t="10m0s",
                    ),
                ],
            ),
        ],
        stitchable_closed_activities=[],
        open_auto_activities=[],
    )
