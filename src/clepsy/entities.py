from datetime import datetime, timedelta, timezone, tzinfo
from enum import StrEnum
from functools import cached_property
from typing import Any, ClassVar, Dict, Literal, NamedTuple, Optional, get_args
from uuid import UUID, uuid4

from baml_py.errors import BamlError
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field

import baml_client.types as baml_types


class MissingUserSettingsError(Exception):
    "Exception raised when user settings are missing."


class Source(StrEnum):
    AUTO = "auto"
    MANUAL = "manual"


class CheckWithError(NamedTuple):
    result: bool
    error: str | None


class ViewMode(StrEnum):
    """Enum representing the different timeline view modes"""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


def get_view_mode_label(mode: "ViewMode") -> str:
    """Return a user-facing label for a ViewMode enum value."""
    match mode:
        case ViewMode.DAILY:
            return "Daily"
        case ViewMode.WEEKLY:
            return "Weekly"
        case ViewMode.MONTHLY:
            return "Monthly"
        case _:
            raise ValueError(f"Unknown ViewMode: {mode}")


class Tag(BaseModel):
    name: str
    description: str


class DBTag(Tag):
    name: str
    description: str
    id: int

    def as_tag(self) -> Tag:
        return Tag(name=self.name, description=self.description)


class TimeSpan(BaseModel):
    start_time: datetime
    end_time: datetime

    @property
    def duration(self) -> timedelta:
        return self.end_time - self.start_time


class ProductivityLevel(StrEnum):
    VERY_PRODUCTIVE = "very_productive"  # deep work
    PRODUCTIVE = "productive"  # useful, lighter tasks
    NEUTRAL = "neutral"  # neither helps nor hurts
    DISTRACTING = "distracting"  # low-value interruptions
    VERY_DISTRACTING = "very_distracting"  # outright time-sink


class Bbox(BaseModel):
    left: int
    top: int
    width: int
    height: int


class WindowInfo(BaseModel):
    title: str
    app_name: str
    bbox: Bbox


class Activity(BaseModel):
    name: str
    description: str
    productivity_level: ProductivityLevel = Field(
        description="Productivity level based on activity and level of focus."
    )
    last_manual_action_time: datetime | None
    source: Source

    @property
    def is_manual(self) -> bool:
        return self.source == Source.MANUAL


class DBActivity(Activity):
    id: int


class Event(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: ClassVar[str] = "event"  # Overwrite in subclasses

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ModelProvider(StrEnum):
    """Enum representing the different model providers"""

    GOOGLE_AI = "google-ai"
    OPENAI = "openai"
    OPENAI_GENERIC = "openai-generic"
    ANTHROPIC = "anthropic"


class GoogleAIConfig(BaseModel):
    model_provider: Literal[ModelProvider.GOOGLE_AI] = ModelProvider.GOOGLE_AI
    model: str
    api_key: Optional[str] = None
    model_base_url: Optional[str] = None

    def __hash__(self):
        return hash(
            (
                self.model_provider,
                self.model_base_url,
                self.model,
                self.api_key,
            )
        )


class OpenAIConfig(BaseModel):
    model_provider: Literal[ModelProvider.OPENAI] = ModelProvider.OPENAI
    model: str
    api_key: Optional[str] = None
    model_base_url: Optional[str] = None

    def __hash__(self):
        return hash(
            (
                self.model_provider,
                self.model_base_url,
                self.model,
                self.api_key,
            )
        )


class OpenAIGenericConfig(BaseModel):
    model_provider: Literal[ModelProvider.OPENAI_GENERIC] = ModelProvider.OPENAI_GENERIC
    model: str
    api_key: Optional[str] = None
    model_base_url: Optional[str] = None

    def __hash__(self):
        return hash(
            (
                self.model_provider,
                self.model_base_url,
                self.model,
                self.api_key,
            )
        )


class AnthropicConfig(BaseModel):
    model_provider: Literal[ModelProvider.ANTHROPIC] = ModelProvider.ANTHROPIC
    model: str
    api_key: Optional[str] = None
    model_base_url: Optional[str] = None

    def __hash__(self):
        return hash(
            (
                self.model_provider,
                self.model_base_url,
                self.model,
                self.api_key,
            )
        )


LLMConfig = GoogleAIConfig | OpenAIConfig | OpenAIGenericConfig | AnthropicConfig


class DesktopInputScreenshotEvent(Event):
    screenshot: Image.Image
    active_window: WindowInfo
    timestamp: datetime
    event_type: ClassVar[str] = "desktop_check_input"


class MobileAppUsageEvent(Event):
    package_name: str
    app_label: str
    timestamp: datetime
    activity_name: Optional[str] = None
    media_metadata: Optional[Dict[str, str]] = None
    notification_text: Optional[str] = None
    event_type: ClassVar[str] = "mobile_app_usage"


class DesktopInputAfkStartEvent(Event):
    time_since_last_user_activity: timedelta
    timestamp: datetime
    event_type: ClassVar[str] = "desktop_afk_event"


DesktopInputEvent = DesktopInputScreenshotEvent | DesktopInputAfkStartEvent
MobileInputEvent = MobileAppUsageEvent


class ProcessedDesktopCheckScreenshotEventVLM(Event):
    llm_description: str
    active_window: WindowInfo
    timestamp: datetime
    event_type: ClassVar[str] = "processed_desktop_check_input_vlm"


class ProcessedDesktopCheckScreenshotEventOCR(Event):
    image_text: str
    active_window: WindowInfo
    timestamp: datetime
    event_type: ClassVar[str] = "processed_desktop_check_input_ocr"
    image_text_post_processed_by_llm: bool


class ImageProcessingApproach(StrEnum):
    VLM = "vlm"
    OCR = "ocr"


class UserSettings(BaseModel):
    timezone: str
    image_model_config: LLMConfig | None
    text_model_config: LLMConfig
    username: str
    productivity_prompt: str = ""
    image_processing_approach: ImageProcessingApproach


class ShutdownEvent(Event):
    event_type: ClassVar[str] = "shutdown"


class ActivityEventType(StrEnum):
    OPEN = "open"
    CLOSE = "close"


class ActivityEvent(BaseModel):
    event_time: datetime
    event_type: ActivityEventType


class NewActivityEventExistingActivity(ActivityEvent):
    activity_id: int


class DBActivityEvent(ActivityEvent):
    id: int
    aggregation_id: int | None
    activity_id: int
    last_manual_action_time: datetime | None


class ActivityEventInsert(ActivityEvent):
    """Insert-only event record (no DB id yet).

    Mirrors DBActivityEvent minus the id, used when inserting new events.
    """

    aggregation_id: int | None
    activity_id: int
    last_manual_action_time: datetime | None


class DBActivitySpec(BaseModel):
    activity: DBActivity
    events: list[DBActivityEvent]

    def __hash__(self):
        return hash((self.activity.id, "activity_spec"))

    @property
    def activity_id(self) -> int:
        return self.activity.id

    @property
    def start_time(self) -> datetime:
        return self.sorted_events[0].event_time

    def end_time(self, horizon: datetime | None = None) -> datetime:
        last_event = self.last_event
        if last_event.event_type == ActivityEventType.OPEN:
            assert horizon, "Must provide horizon if last event is OPEN"
            return horizon

        return last_event.event_time

    def time_spans(self, horizon: datetime | None) -> list[TimeSpan]:
        spans: list[TimeSpan] = []

        for open_event, close_event in zip(self.sorted_events, self.sorted_events[1:]):
            spans.append(
                TimeSpan(
                    start_time=open_event.event_time, end_time=close_event.event_time
                )
            )

        if self.sorted_events[-1].event_type == ActivityEventType.OPEN:
            assert horizon, "Must provide horizon if last event is OPEN"
            spans.append(
                TimeSpan(start_time=self.sorted_events[-1].event_time, end_time=horizon)
            )

        return spans

    def total_span(self, horizon: datetime | None) -> TimeSpan:
        first_event = self.sorted_events[0]
        last_event = self.sorted_events[-1]
        if last_event.event_type == ActivityEventType.CLOSE:
            return TimeSpan(
                start_time=first_event.event_time, end_time=last_event.event_time
            )
        else:
            assert horizon, "Must provide horizon if last event is OPEN"
            return TimeSpan(start_time=first_event.event_time, end_time=horizon)

    @cached_property
    def sorted_events(self) -> list[DBActivityEvent]:
        """Returns the events sorted by event time."""
        return sorted(self.events, key=lambda x: x.event_time)

    @property
    def last_event(self) -> DBActivityEvent:
        """Returns the last event based on event time."""
        return self.sorted_events[-1]

    @property
    def ended(self) -> bool:
        return self.end_time is not None

    def to_tz(self, tz: tzinfo) -> "DBActivitySpec":
        new_events = []
        for event in self.events:
            new_event = event.model_copy()
            new_event.event_time = event.event_time.astimezone(tz)
            new_events.append(new_event)
        return DBActivitySpec(activity=self.activity, events=new_events)


class DBActivitySpecWithTags(DBActivitySpec):
    """Activity spec with associated tags"""

    tags: list[DBTag] = []

    def to_tz(self, tz: tzinfo) -> "DBActivitySpecWithTags":
        # First get the base conversion done by the parent class
        base_spec = super().to_tz(tz)

        # Then create a new DBActivitySpecWithTags instance with the converted data
        # but keeping our tags
        return DBActivitySpecWithTags(
            activity=base_spec.activity, events=base_spec.events, tags=self.tags
        )

    def __hash__(self):
        assert self.activity.id is not None, "Activity ID must be set for hashing"
        return hash((self.activity.id, "activity_spec_with_tags"))

    def __eq__(self, other) -> bool:
        assert (
            self.activity.id is not None
        ), "Activity ID must be set for equality check"
        return self.activity.id == other.activity.id


class DBActivitySpecWithTagsAndSessions(DBActivitySpecWithTags):
    """Activity spec with tags, finalized session, and candidate sessions.

    An activity can belong to at most one finalized session (enforced by UNIQUE constraint),
    but can belong to multiple candidate sessions.
    """

    session: "DBSession | None" = None
    candidate_sessions: list["DBCandidateSession"] = []

    def to_tz(self, tz: tzinfo) -> "DBActivitySpecWithTagsAndSessions":
        # First get the base conversion done by the parent class
        base_spec = super().to_tz(tz)

        # Then create a new instance with the converted data but keeping relationships
        return DBActivitySpecWithTagsAndSessions(
            activity=base_spec.activity,
            events=base_spec.events,
            tags=base_spec.tags,
            session=self.session,
            candidate_sessions=self.candidate_sessions,
        )

    def __hash__(self):
        assert self.activity.id is not None, "Activity ID must be set for hashing"
        return hash((self.activity.id, "activity_spec_with_tags_and_sessions"))

    def __eq__(self, other) -> bool:
        assert (
            self.activity.id is not None
        ), "Activity ID must be set for equality check"
        return self.activity.id == other.activity.id


class Aggregation(BaseModel):
    start_time: datetime
    end_time: datetime
    first_timestamp: datetime
    last_timestamp: datetime


class DBAggregation(Aggregation):
    id: int


class ActivityWithLatestEvent(NamedTuple):
    activity: Activity
    latest_event: ActivityEvent


class DBActivityWithLatestEvent(NamedTuple):
    activity: DBActivity
    latest_event: DBActivityEvent
    latest_aggregation: DBAggregation

    model_config = ConfigDict(arbitrary_types_allowed=True)


class TagMapping(BaseModel):
    activity_id: int
    tag_id: int


Events = (
    DesktopInputEvent
    | ProcessedDesktopCheckScreenshotEventOCR
    | ProcessedDesktopCheckScreenshotEventVLM
    | MobileAppUsageEvent
    | ShutdownEvent
)


AggregationInputEvent = (
    ProcessedDesktopCheckScreenshotEventOCR
    | ProcessedDesktopCheckScreenshotEventVLM
    | MobileAppUsageEvent
    | DesktopInputAfkStartEvent
)


class SourceType(StrEnum):
    DESKTOP = "desktop"
    MOBILE = "mobile"


class ActivityExtras(BaseModel):
    productivity_level: ProductivityLevel
    tags: list[DBTag]


class ActivityStitchingInput(BaseModel):
    name: str
    description: str


class AggregatorCoreOutput(BaseModel):
    new_activities: dict[str, baml_types.ActivityMetadata]
    new_activity_events: list[baml_types.Event]
    stitched_activities_events: list[NewActivityEventExistingActivity]
    unstitched_activities_close_events: list[NewActivityEventExistingActivity]
    activities_to_update: list[tuple[int, dict[str, str]]]


# ---- Data Sources (devices/integrations) ----
class SourceStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


class DeviceSource(BaseModel):
    name: str
    source_type: SourceType
    status: SourceStatus = SourceStatus.ACTIVE


class DBDeviceSource(DeviceSource):
    id: int
    token_hash: str
    last_seen: datetime | None = None
    created_at: datetime


class GoalMetric(StrEnum):
    TOTAL_ACTIVITY_DURATION = "total_activity_duration"
    AVG_PRODUCTIVITY_LEVEL = "productivity_level"


class MetricOperator(StrEnum):
    EQUAL = "equal"
    NOT_EQUAL = "not_equal"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"


class IncludeMode(StrEnum):
    ALL = "all"
    ANY = "any"


# ---- Pairing API entities ----
class SourceEnrollmentCode(BaseModel):
    id: int
    code_hash: str
    expires_at: datetime | None


class SourcePairRequest(BaseModel):
    code: str
    device_name: str
    source_type: SourceType


class SourcePairResponse(BaseModel):
    source_id: int
    device_token: str


DaysOfWeek = Literal[
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"
]


class GoalPeriod(StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class BaseGoalDefinition(BaseModel):
    """Editable per-definition properties (domain shape)."""

    name: str
    description: Optional[str] = None
    include_mode: IncludeMode
    day_filter: list[DaysOfWeek] | None = None
    productivity_filter: list[ProductivityLevel] | None = None
    time_filter: list[tuple[str, str]] | None = None
    effective_from: datetime


AvgProductivityOperators = Literal[
    MetricOperator.LESS_THAN,
    MetricOperator.GREATER_THAN,
]

avg_productivity_operators = list(get_args(AvgProductivityOperators))


class BaseGoal(BaseModel):
    """Immutable per-goal properties (domain shape)."""

    paused_since: Optional[datetime] = None
    timezone: str
    period: GoalPeriod


TotalActivityDurationOperators = Literal[
    MetricOperator.LESS_THAN, MetricOperator.GREATER_THAN
]

total_activity_duration_operators = list(get_args(TotalActivityDurationOperators))


class AvgProductivityGoalDefinition(BaseGoalDefinition):
    target_value: float
    metric_params: None = None


class TotalActivityDurationGoalDefinition(BaseGoalDefinition):
    target_value: timedelta
    metric_params: None = None


GoalDefinition = AvgProductivityGoalDefinition | TotalActivityDurationGoalDefinition


class EvalState(StrEnum):
    OK = "ok"
    PARTIAL = "partial"
    NA = "na"
    PAUSED = "paused"


class AvgProductivityGoal(BaseGoal):
    metric: Literal[GoalMetric.AVG_PRODUCTIVITY_LEVEL] = (
        GoalMetric.AVG_PRODUCTIVITY_LEVEL
    )
    operator: AvgProductivityOperators


class TotalActivityDurationGoal(BaseGoal):
    metric: Literal[GoalMetric.TOTAL_ACTIVITY_DURATION] = (
        GoalMetric.TOTAL_ACTIVITY_DURATION
    )
    operator: TotalActivityDurationOperators


Goal = AvgProductivityGoal | TotalActivityDurationGoal


# --- DB variants base ---


class DBBaseGoal(BaseGoal):
    """DB-backed goal with identifiers and timestamps, extends BaseGoal."""

    id: int
    created_at: datetime


class DBAvgProductivityGoal(DBBaseGoal):
    metric: Literal[GoalMetric.AVG_PRODUCTIVITY_LEVEL] = (
        GoalMetric.AVG_PRODUCTIVITY_LEVEL
    )
    operator: AvgProductivityOperators


class DBTotalActivityDurationGoal(DBBaseGoal):
    metric: Literal[GoalMetric.TOTAL_ACTIVITY_DURATION] = (
        GoalMetric.TOTAL_ACTIVITY_DURATION
    )
    operator: TotalActivityDurationOperators


DBGoal = DBAvgProductivityGoal | DBTotalActivityDurationGoal


"""GoalDefinition DB variants"""


class DBBaseGoalDefinition(BaseGoalDefinition):
    id: int
    goal_id: int


class DBAvgProductivityGoalDefinition(
    DBBaseGoalDefinition, AvgProductivityGoalDefinition
):
    pass


class DBTotalActivityDurationGoalDefinition(
    DBBaseGoalDefinition, TotalActivityDurationGoalDefinition
):
    pass


DBGoalDefinition = (
    DBAvgProductivityGoalDefinition | DBTotalActivityDurationGoalDefinition
)


class GoalResult(BaseModel):
    goal_definition_id: int
    period_start: datetime
    period_end: datetime
    metric_value: Any
    success: bool | None
    eval_state: EvalState
    eval_state_reason: str | None


class DBGoalResult(GoalResult):
    id: int
    created_at: datetime


class BaseGoalProgressCurrent(BaseModel):
    """Common fields for current progress."""

    goal_definition_id: int
    period_start: datetime
    period_end: datetime
    success: bool | None
    eval_state: EvalState
    eval_state_reason: str | None
    updated_at: datetime


class ProductivityGoalProgressCurrent(BaseGoalProgressCurrent):
    """Current progress for AVG_PRODUCTIVITY_LEVEL. metric_value in [0,1]."""

    metric_value: float


class TotalActivityDurationGoalProgressCurrent(BaseGoalProgressCurrent):
    """Current progress for TOTAL_ACTIVITY_DURATION. metric_value in seconds."""

    metric_value: float

    @property
    def metric_value_td(self) -> timedelta:
        return timedelta(seconds=float(self.metric_value))


GoalProgressCurrent = (
    ProductivityGoalProgressCurrent | TotalActivityDurationGoalProgressCurrent
)


class GoalWithLatestResult(BaseModel):
    goal: DBGoal
    definition: DBGoalDefinition
    include_tags: list[DBTag] = []
    exclude_tags: list[DBTag] = []
    latest_result: GoalResult | None
    last_successes: list[bool] = Field(
        description="List of latest success states for the goal"
    )


class AADS(StrEnum):
    LLM_API_KEY = "llm_api_key"


class WorkerSignalSeverity(StrEnum):
    ERROR = "error"
    HEARTBEAT = "heartbeat"


class WorkerSignalBase(BaseModel):
    timestamp: datetime = datetime.now(tz=timezone.utc)


class BamlErrorSignal(WorkerSignalBase):
    exception: BamlError
    severity: Literal[WorkerSignalSeverity.ERROR] = WorkerSignalSeverity.ERROR

    class Config:
        arbitrary_types_allowed = True


class SettingsNotSetSignal(WorkerSignalBase):
    severity: Literal[WorkerSignalSeverity.ERROR] = WorkerSignalSeverity.ERROR


WorkerSignal = BamlErrorSignal | SettingsNotSetSignal

WorkerName = Literal[
    "DesktopCheckWorker",
    "AggregatorWorker",
]


class IsolatedTimelineQCPolicy(StrEnum):
    NEVER = "never"
    WHEN_PROGRAMMATIC_ERRRORS = "when_programmatic_errors"
    ALWAYS = "always"


class SessionToActivity(BaseModel):
    session_id: int
    activity_id: int


class Session(BaseModel):
    name: str
    llm_id: str


class SessionSpec(BaseModel):
    session: Session
    activity_ids: list[int]


class DBSession(Session):
    id: int
    created_at: datetime
    sessionization_run_id: int


class DBSessionSpec(BaseModel):
    session: DBSession
    activity_ids: list[int]


class SessionizationRun(BaseModel):
    candidate_creation_start: datetime
    candidate_creation_end: datetime
    overlap_start: datetime | None
    right_tail_end: datetime | None
    finalized_horizon: datetime | None


class DBSessionizationRun(SessionizationRun):
    id: int
    created_at: datetime


class CandidateSession(BaseModel):
    name: str
    llm_id: str

    def __hash__(self):
        return hash((self.name, self.llm_id))


class DBCandidateSession(CandidateSession):
    id: int
    created_at: datetime
    sessionization_run_id: int

    def __hash__(
        self,
    ):
        return hash((self.id, "candidate_session"))


class CandidateSessionToActivity(BaseModel):
    candidate_session_id: int
    activity_id: int


class CandidateSessionSpec(BaseModel):
    session: CandidateSession
    activity_ids: list[int]


class DBCandidateSessionSpec(BaseModel):
    session: DBCandidateSession
    activity_ids: list[int]

    def __hash__(self):
        return hash((self.session.id, tuple(self.activity_ids)))
