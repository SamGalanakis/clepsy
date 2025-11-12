import asyncio
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

from loguru import logger

from baml_client import b
from baml_client.type_builder import TypeBuilder
import baml_client.types as baml_types
from clepsy import utils
from clepsy.config import config
from clepsy.db import get_db_connection
from clepsy.db.queries import (
    delete_candidate_session_to_activity_by_activity_ids,
    delete_candidate_sessions_by_ids,
    delete_candidate_sessions_without_activities,
    insert_candidate_session_to_activity,
    insert_candidate_sessions,
    insert_session_to_activity,
    insert_sessionization_run,
    insert_sessions,
    select_candidate_session_specs,
    select_last_aggregation,
    select_latest_sessionization_run,
    select_specs_with_tags_in_time_range,
    select_user_settings,
)
from clepsy.entities import (
    CandidateSession,
    CandidateSessionSpec,
    CandidateSessionToActivity,
    DBActivitySpec,
    DBActivitySpecWithTags,
    DBCandidateSession,
    DBCandidateSessionSpec,
    LLMConfig,
    Session,
    SessionizationRun,
    SessionSpec,
    SessionToActivity,
    Tag,
    TimeSpan,
)
from clepsy.llm import create_client_registry


async def detect_sessions(
    specs_in_time_range: list[DBActivitySpecWithTags],
    preexisting_sessions: list[CandidateSession],
    window_end: datetime,
    llm_config: LLMConfig,
) -> list[CandidateSessionSpec]:
    # Extract unique tags from all activity specs
    all_tags: dict[int, Tag] = {}
    for spec in specs_in_time_range:
        for db_tag in spec.tags:
            if db_tag.id not in all_tags:
                all_tags[db_tag.id] = Tag(
                    name=db_tag.name, description=db_tag.description
                )

    baml_tags = [
        baml_types.Tag(name=tag.name, description=tag.description)
        for tag in all_tags.values()
    ]

    baml_activities = []

    seen_names = defaultdict(lambda: 0)

    sorted_specs_in_time_range = sorted(
        specs_in_time_range, key=lambda spec: spec.start_time
    )
    llm_id_to_activity_id = {}

    for activity_spec in sorted_specs_in_time_range:
        llm_id = utils.activity_name_to_id(activity_spec.activity.name)
        current_count = seen_names[llm_id]

        duration = utils.calculate_duration(
            window_start=None,
            window_end=window_end,
            events=activity_spec.sorted_events,
        )

        seen_names[llm_id] += 1
        if current_count > 0:
            llm_id = f"{llm_id}_{current_count}"

        llm_id_to_activity_id[llm_id] = activity_spec.activity.id

        baml_activities.append(
            baml_types.SessionActivityMetadata(
                activity_id=llm_id,
                name=activity_spec.activity.name,
                description=activity_spec.activity.description,
                duration=utils.human_delta(duration),
            )
        )

    if preexisting_sessions:
        preexisting_sessions_baml = [
            baml_types.SessionIdentifier(session_id=x.llm_id, title=x.name)
            for x in preexisting_sessions
        ]
    else:
        preexisting_sessions_baml = []

    tb = TypeBuilder()

    for llm_id in llm_id_to_activity_id.keys():
        tb.ActivityIds.add_value(llm_id)

    client = create_client_registry(
        llm_config=llm_config, name="TextClient", set_primary=True
    )

    candidate_sessions_llm = await b.ExtractSessions(
        activities=baml_activities,
        tags=baml_tags,
        preexisting_sessions=preexisting_sessions_baml,
        baml_options={"client_registry": client, "tb": tb},
    )

    candidate_session_specs = []

    for candidate_session_llm in candidate_sessions_llm:
        session = CandidateSession(
            name=candidate_session_llm.session.title,
            llm_id=candidate_session_llm.session.session_id,
        )

        activity_ids = [
            llm_id_to_activity_id[activity_id]
            for activity_id in candidate_session_llm.activity_ids
        ]

        candidate_session_specs.append(
            CandidateSessionSpec(session=session, activity_ids=activity_ids)
        )

    return candidate_session_specs


@dataclass
class CandidateProposalOutput:
    new_mappings: dict[CandidateSession, set[int]]
    existing_mappings: dict[DBCandidateSession, set[int]]


async def propose_candidate_sessions_for_island(
    island: list[DBActivitySpecWithTags],
    window_end: datetime,
    carry_over_session_specs: list[DBCandidateSessionSpec],
    max_activities_per_session_llm_call: int,
    llm_config: LLMConfig,
) -> CandidateProposalOutput:
    sub_arrays = utils.overlapping_subarray_split(
        island,
        max_subarray_length=max_activities_per_session_llm_call,
        overlap_percentage=0.2,
    )

    mapping_for_new_sessions = defaultdict(set)
    mappings_for_carry_over_sessions = defaultdict(set)

    carry_over_session_to_db = {
        CandidateSession(name=spec.session.name, llm_id=spec.session.llm_id): spec
        for spec in carry_over_session_specs
    }

    overlap_sessions = list(carry_over_session_to_db.keys())

    for index, sub_array in enumerate(sub_arrays):
        is_last = index == len(sub_arrays) - 1
        candidate_session_specs = await detect_sessions(
            specs_in_time_range=sub_array,
            preexisting_sessions=overlap_sessions,
            window_end=window_end,
            llm_config=llm_config,
        )

        for session_spec in candidate_session_specs:
            if db_spec := carry_over_session_to_db.get(session_spec.session):
                # Only add new mappings - existing ones are already in DB
                new_mappings = [
                    x
                    for x in session_spec.activity_ids
                    if x not in db_spec.activity_ids
                ]

                mappings_for_carry_over_sessions[db_spec.session].update(new_mappings)
            else:
                mapping_for_new_sessions[session_spec.session].update(
                    session_spec.activity_ids
                )

        if not is_last:
            next_sub_array = sub_arrays[index + 1]
            overlap_activity_ids = {spec.activity_id for spec in sub_array} & {
                spec.activity_id for spec in next_sub_array
            }
            overlap_sessions = []
            for session_spec in candidate_session_specs:
                in_overlap = any(
                    activity_id in overlap_activity_ids
                    for activity_id in session_spec.activity_ids
                )
                if in_overlap:
                    overlap_sessions.append(session_spec.session)

    return CandidateProposalOutput(
        new_mappings=dict(mapping_for_new_sessions),
        existing_mappings=dict(mappings_for_carry_over_sessions),
    )


@dataclass
class PickedSession:
    L: int
    R: int
    start: datetime
    end: datetime
    duration: timedelta
    purity: float
    activity_ids: List[int]


@dataclass
class Interval:
    name: str
    llm_id: str
    L: int
    R: int
    start: datetime
    end: datetime
    dur_s: float
    purity: float
    chosen_ids: list[int]  # candidate's activity_ids within [L..R], in time order


def build_island_arrays(
    island: list[DBActivitySpecWithTags], island_end: datetime
) -> dict[str, list]:
    specs_sorted: list[DBActivitySpec] = sorted(island, key=lambda a: a.start_time)
    starts: list[datetime] = []
    ends: list[datetime] = []
    secs: list[float] = []
    ids: list[int] = []
    for spec in specs_sorted:
        spans: list[TimeSpan] = spec.time_spans(horizon=island_end)
        if not spans:
            continue
        s = spans[0].start_time
        e = spans[-1].end_time
        total = timedelta(0)
        for ts in spans:
            total += ts.duration
        starts.append(s)
        ends.append(e)
        secs.append(float(total.total_seconds()))
        ids.append(spec.activity_id)
    return {"starts": starts, "ends": ends, "secs": secs, "ids": ids}


def pick_best_window_for_candidate(
    starts: list[datetime],
    ends: list[datetime],
    secs: list[float],
    ids: list[int],
    candidate_ids: set[int],
    min_activities: int,
    min_purity: float,
    min_length: timedelta,
    max_gap: timedelta,
) -> Optional[Interval]:
    n = len(ids)
    if n == 0:
        return None
    inc_secs: list[float] = [
        secs[i] if ids[i] in candidate_ids else 0.0 for i in range(n)
    ]
    inc_flags: list[int] = [1 if ids[i] in candidate_ids else 0 for i in range(n)]
    min_len_s: float = float(min_length.total_seconds())
    max_gap_s: float = float(max_gap.total_seconds())

    def internal_gap_ok(L: int, R: int) -> tuple[bool, int]:
        prev_idx: Optional[int] = None
        for i in range(L, R + 1):
            if inc_flags[i] == 1:
                if prev_idx is not None:
                    gap_s = (starts[i] - ends[prev_idx]).total_seconds()
                    if gap_s > max_gap_s:
                        return False, prev_idx + 1
                prev_idx = i
        return True, L

    best: Optional[Interval] = None
    L = 0
    sum_inc = 0.0
    sum_inc_cnt = 0

    for R in range(n):
        sum_inc += inc_secs[R]
        sum_inc_cnt += inc_flags[R]

        while L <= R:
            span_s = (ends[R] - starts[L]).total_seconds()
            if span_s <= 0:
                sum_inc -= inc_secs[L]
                sum_inc_cnt -= inc_flags[L]
                L += 1
                continue

            purity = min(sum_inc / span_s, 1.0)
            if purity < min_purity:
                sum_inc -= inc_secs[L]
                sum_inc_cnt -= inc_flags[L]
                L += 1
                continue

            ok, suggested_L = internal_gap_ok(L, R)
            if not ok:
                while L < suggested_L:
                    sum_inc -= inc_secs[L]
                    sum_inc_cnt -= inc_flags[L]
                    L += 1
                continue

            cand_cnt = sum_inc_cnt
            if cand_cnt >= min_activities and span_s >= min_len_s:
                chosen_ids: list[int] = [
                    ids[i] for i in range(L, R + 1) if inc_flags[i] == 1
                ]
                candidate = Interval(
                    name="",
                    llm_id="",
                    L=L,
                    R=R,
                    start=starts[L],
                    end=ends[R],
                    dur_s=span_s,
                    purity=purity,
                    chosen_ids=chosen_ids,
                )
                if (
                    best is None
                    or candidate.dur_s > best.dur_s
                    or (
                        candidate.dur_s == best.dur_s and candidate.purity > best.purity
                    )
                ):
                    best = candidate
            break  # keep L as far left as constraints allow for this R
    return best


def extract_windows_for_candidate(
    starts: list[datetime],
    ends: list[datetime],
    secs: list[float],
    ids: list[int],
    candidate_ids: set[int],
    min_activities: int,
    min_purity: float,
    min_length: timedelta,
    max_gap: timedelta,
) -> list[Interval]:
    """Extract all disjoint (by activity_id) valid windows for one candidate."""
    windows: list[Interval] = []
    remaining_ids: set[int] = set(candidate_ids)
    seen: set[tuple[int, ...]] = set()

    while remaining_ids:
        iv = pick_best_window_for_candidate(
            starts=starts,
            ends=ends,
            secs=secs,
            ids=ids,
            candidate_ids=remaining_ids,
            min_activities=min_activities,
            min_purity=min_purity,
            min_length=min_length,
            max_gap=max_gap,
        )
        if not iv or not iv.chosen_ids:
            break

        # ensure progress + dedupe
        chosen_tuple = tuple(iv.chosen_ids)
        if chosen_tuple in seen:
            break
        seen.add(chosen_tuple)

        windows.append(iv)

        # consume chosen ids so next pass can find another disjoint window (if any)
        for aid in iv.chosen_ids:
            remaining_ids.discard(aid)

    return windows


def validate_and_select_sessions(
    island: list[DBActivitySpecWithTags],
    island_end: datetime,
    candidate_specs: list[CandidateSessionSpec],
    min_activities: int,
    min_purity: float,
    min_length: timedelta,
    max_gap: timedelta,
) -> list[SessionSpec]:
    """
    - Generates multiple valid windows per candidate (disjoint in activity IDs).
    - Selects a non-overlapping set (by activity_id) maximizing total duration of covered activities.
    - Returns finalized SessionSpec list with trimmed, ordered activity_ids.
    """
    arrays = build_island_arrays(island, island_end)
    starts: list[datetime] = arrays["starts"]
    ends: list[datetime] = arrays["ends"]
    secs: list[float] = arrays["secs"]
    ids: list[int] = arrays["ids"]

    # Map activity_id -> duration (seconds)
    id2dur: dict[int, float] = {ids[i]: secs[i] for i in range(len(ids))}

    # 1) Build all valid windows (intervals) from candidates
    intervals: list[Interval] = []
    for c in candidate_specs:
        cand_set: set[int] = set(c.activity_ids)
        ivs = extract_windows_for_candidate(
            starts=starts,
            ends=ends,
            secs=secs,
            ids=ids,
            candidate_ids=cand_set,
            min_activities=min_activities,
            min_purity=min_purity,
            min_length=min_length,
            max_gap=max_gap,
        )
        for iv in ivs:
            iv.name = c.session.name
            iv.llm_id = c.session.llm_id
            intervals.append(iv)

    if not intervals:
        return []

    # 2) Greedy maximum coverage under "no shared activity_id"
    covered: set[int] = set()
    chosen: list[Interval] = []

    def marginal_gain(iv: Interval) -> float:
        return sum(id2dur[aid] for aid in iv.chosen_ids if aid not in covered)

    # Recompute marginal gains each step until no positive gain
    remaining: list[Interval] = intervals[:]
    while remaining:
        # pick best by marginal gain, tie-break by purity then longer dur
        best_iv = max(remaining, key=lambda x: (marginal_gain(x), x.purity, x.dur_s))
        gain = marginal_gain(best_iv)
        if gain <= 0:
            break
        # accept
        chosen.append(best_iv)
        for aid in best_iv.chosen_ids:
            covered.add(aid)
        # drop best_iv and any interval that now conflicts (shares an activity)
        remaining = [
            iv
            for iv in remaining
            if iv is not best_iv and not any(a in covered for a in iv.chosen_ids)
        ]

    # 3) Build output specs
    result: list[SessionSpec] = [
        SessionSpec(
            session=Session(name=iv.name, llm_id=iv.llm_id), activity_ids=iv.chosen_ids
        )
        for iv in chosen
    ]
    return result


@dataclass
class Island:
    activity_specs: list[DBActivitySpecWithTags]
    left_connected: bool
    right_connected: bool

    @property
    def is_double_connected(self) -> bool:
        return self.left_connected and self.right_connected


def extract_valid_islands(
    specs_in_time_range: list[DBActivitySpecWithTags],
    window_end: datetime,
    previous_window_last_active: datetime | None,
    max_session_gap: timedelta,
    min_activities_per_session: int,
    min_session_length: timedelta,
) -> list[Island]:
    """Partition coverage into left tail, middle islands, and right tail."""

    def is_land_valid(specs: list[DBActivitySpecWithTags]) -> bool:
        if len(specs) < min_activities_per_session:
            return False

        start_time = min(spec.start_time for spec in specs)
        end_time = max(spec.end_time(window_end) for spec in specs)

        return (end_time - start_time) >= min_session_length

    assert specs_in_time_range, "specs_in_time_range must not be empty"
    specs_in_time_range = sorted(specs_in_time_range, key=lambda spec: spec.start_time)
    full_activity_spans = [x.total_span(window_end) for x in specs_in_time_range]

    island_split_indexes = utils.extract_islands(
        full_activity_spans, max_gap=max_session_gap, assume_sorted=True
    )

    first_island_left_connected = previous_window_last_active is not None and (
        full_activity_spans[0].start_time - previous_window_last_active
        <= max_session_gap
    )
    gap_between_last_activity_and_window_end = (
        window_end - full_activity_spans[-1].end_time > max_session_gap
    )

    if island_split_indexes:
        segments = utils.split_by_indices(specs_in_time_range, island_split_indexes)
    else:
        segments = [specs_in_time_range]

    islands = []

    first_segment = segments[0]
    last_segment = segments[-1]

    if len(segments) == 1:
        islands.append(
            Island(
                activity_specs=first_segment,
                left_connected=first_island_left_connected,
                right_connected=not gap_between_last_activity_and_window_end,
            )
        )

    elif len(segments) >= 2:
        islands.append(
            Island(
                activity_specs=first_segment,
                left_connected=first_island_left_connected,
                right_connected=False,
            )
        )
        islands.append(
            Island(
                activity_specs=last_segment,
                left_connected=False,
                right_connected=not gap_between_last_activity_and_window_end,
            )
        )

        for middle_segment in segments[1:-1]:
            if is_land_valid(middle_segment):
                islands.append(
                    Island(
                        activity_specs=middle_segment,
                        left_connected=False,
                        right_connected=False,
                    )
                )

    return islands


@dataclass
class RightConnectedIslandResult:
    new_candidate_session_specs: list[CandidateSessionSpec]
    new_mappings_existing_candidate_sessions: dict[DBCandidateSession, set[int]]
    session_specs_to_create: list[SessionSpec]
    finalized_horizon: datetime
    overlap_start: datetime
    right_tail_end: datetime
    activity_ids_to_delete_from_candidate_sessions: list[int]


@dataclass
class RightIsolatedIslandResult:
    candidate_session_ids_to_delete: list[int]
    session_specs_to_create: list[SessionSpec]


@dataclass
class FinalizeRightConnectedIslandOutput:
    finalized_horizon: datetime
    session_specs_to_create: list[SessionSpec]
    activity_ids_to_delete_from_candidate_sessions: list[int]


def finalize_right_connected_island(
    island: list[DBActivitySpecWithTags],
    island_end: datetime,  # window_end
    candidate_specs: list[CandidateSessionSpec | DBCandidateSessionSpec],
    overlap_start: datetime,  # F = window_end - overlap_duration
    min_activities: int,
    min_purity: float,
    min_length: timedelta,
    max_gap: timedelta,
) -> FinalizeRightConnectedIslandOutput:
    """
    Finalize safe sessions on a right-connected island.

    Logic:
      - F = overlap_start.
      - tail_ids = activities with any time > F.
      - Split each candidate into L_ids (end<=F) and R_ids (start>F).
      - If R_ids is empty -> candidate is wholly left -> SAFE.
      - Else (crosses F): if (min_start(R_ids) - max_end(L_ids)) > max_gap -> SAFE (no legal bridge).
        Otherwise -> UNSAFE (might bridge next window), skip for now.
      - Build prefix_island = all activities with end<=F (keep non-candidate atoms for purity/gaps).
      - Run validate_and_select_sessions on prefix_island with only SAFE candidates (L_ids trimmed).
      - Return (finalized_sessions, reconsider_from=F).
    """
    F = overlap_start

    # Build quick index: activity_id -> (start, end) with horizon for OPEN
    id2start: dict[int, datetime] = {}
    id2end: dict[int, datetime] = {}
    prefix_island: list[DBActivitySpecWithTags] = []
    for spec in island:
        s = spec.start_time
        e = spec.end_time(horizon=island_end)  # your API
        id2start[spec.activity_id] = s
        id2end[spec.activity_id] = e
        if e <= F:
            prefix_island.append(spec)

    if not prefix_island or not candidate_specs:
        return FinalizeRightConnectedIslandOutput(
            finalized_horizon=F,
            session_specs_to_create=[],
            activity_ids_to_delete_from_candidate_sessions=[],
        )

    # Partition candidates and keep only SAFE left chunks
    # Also track which activity IDs come from DBCandidateSessionSpec (for deletion tracking)
    safe_left_candidates: list[CandidateSessionSpec] = []
    db_candidate_safe_left_activity_ids: set[int] = set()

    for c in candidate_specs:
        is_db_candidate = isinstance(c, DBCandidateSessionSpec)

        L_ids: list[int] = []
        R_ids: list[int] = []
        for aid in c.activity_ids:
            s = id2start.get(aid)
            e = id2end.get(aid)
            if s is None or e is None:
                continue
            if e <= F:
                L_ids.append(aid)
            elif s > F:
                R_ids.append(aid)
            else:
                # An activity straddling F (shouldn't happen with atom spans), treat as right
                R_ids.append(aid)

        if not L_ids:
            # nothing to finalize on the left for this candidate
            continue

        if not R_ids:
            # wholly left -> safe
            safe_left_candidates.append(
                CandidateSessionSpec(
                    session=CandidateSession(
                        name=c.session.name, llm_id=c.session.llm_id
                    ),
                    activity_ids=sorted(L_ids, key=lambda x: id2start[x]),
                )
            )
            # Track DB candidate activity IDs that are being finalized
            if is_db_candidate:
                db_candidate_safe_left_activity_ids.update(L_ids)
            continue

        # crosses F -> apply no-bridge test
        e_left = max(id2end[aid] for aid in L_ids)
        s_right = min(id2start[aid] for aid in R_ids)
        if (s_right - e_left) > max_gap:
            # cannot legally bridge across F -> safe to finalize left chunk now
            safe_left_candidates.append(
                CandidateSessionSpec(
                    session=CandidateSession(
                        name=c.session.name, llm_id=c.session.llm_id
                    ),
                    activity_ids=sorted(L_ids, key=lambda x: id2start[x]),
                )
            )
            # Track DB candidate activity IDs that are being finalized
            if is_db_candidate:
                db_candidate_safe_left_activity_ids.update(L_ids)
        # else: unsafe; skip (leave for next window)

    if not safe_left_candidates:
        return FinalizeRightConnectedIslandOutput(
            finalized_horizon=F,
            session_specs_to_create=[],
            activity_ids_to_delete_from_candidate_sessions=[],
        )

    # Validate & select on the left prefix only, with safe candidates
    finalized: list[SessionSpec] = validate_and_select_sessions(
        island=prefix_island,
        island_end=F,  # close OPENs at F
        candidate_specs=safe_left_candidates,  # only safe left chunks
        min_activities=min_activities,
        min_purity=min_purity,
        min_length=min_length,
        max_gap=max_gap,
    )

    # We only need to reconsider from F next window (LLM sees overlap >= F)
    reconsider_from = F
    return FinalizeRightConnectedIslandOutput(
        finalized_horizon=reconsider_from,
        session_specs_to_create=finalized,
        activity_ids_to_delete_from_candidate_sessions=list(
            db_candidate_safe_left_activity_ids
        ),
    )


def finalize_isolated_carry_over_sessions(
    carry_over_candidate_session_specs: list[DBCandidateSessionSpec],
    specs_not_finalized: list[DBActivitySpecWithTags],
    candidate_creation_interval_end: datetime,
) -> tuple[list[SessionSpec], list[int]]:
    """
    Finalize carry-over candidate sessions from previous window that are isolated (not connected to current window).
    Returns (sessions_to_create, candidate_session_ids_to_delete).
    """
    sessions_to_create: list[SessionSpec] = []
    candidate_session_ids_to_delete: list[int] = []

    if not carry_over_candidate_session_specs or not specs_not_finalized:
        return sessions_to_create, candidate_session_ids_to_delete

    relevant_session_specs = [
        spec
        for spec in carry_over_candidate_session_specs
        if any(
            activity_id in spec.activity_ids
            for activity_id in (
                activity_spec.activity_id for activity_spec in specs_not_finalized
            )
        )
    ]

    if relevant_session_specs:
        sessions_to_create = validate_and_select_sessions(
            island=specs_not_finalized,
            island_end=candidate_creation_interval_end,
            candidate_specs=[
                CandidateSessionSpec(
                    session=CandidateSession(
                        name=spec.session.name, llm_id=spec.session.llm_id
                    ),
                    activity_ids=spec.activity_ids,
                )
                for spec in relevant_session_specs
            ],
            min_activities=config.min_activities_per_session,
            min_purity=config.min_session_purity,
            min_length=config.min_session_length,
            max_gap=config.max_session_gap,
        )
        candidate_session_ids_to_delete = [
            spec.session.id for spec in relevant_session_specs
        ]

    return sessions_to_create, candidate_session_ids_to_delete


async def finalize_carry_over_sessions_and_save(
    carry_over_candidate_session_specs: list[DBCandidateSessionSpec],
    specs_not_finalized: list[DBActivitySpecWithTags],
    candidate_creation_interval_start: datetime,
    candidate_creation_interval_end: datetime,
    finalized_horizon: datetime | None = None,
    overlap_start: datetime | None = None,
    right_tail_end: datetime | None = None,
) -> None:
    """
    Finalize carry-over candidate sessions from previous window and save sessionization run.
    Used for early exits when there are no new activities or no valid islands.
    """
    sessions_to_create, candidate_session_ids_to_delete = (
        finalize_isolated_carry_over_sessions(
            carry_over_candidate_session_specs=carry_over_candidate_session_specs,
            specs_not_finalized=specs_not_finalized,
            candidate_creation_interval_end=candidate_creation_interval_end,
        )
    )

    logger.info(
        "Finalizing carry-over window {} -> {} | carry-over specs: {} | overlap specs: {}",
        candidate_creation_interval_start,
        candidate_creation_interval_end,
        len(carry_over_candidate_session_specs),
        len(specs_not_finalized),
    )
    if specs_not_finalized:
        logger.info(
            "Overlap activity coverage: {} unique activities",
            len({spec.activity_id for spec in specs_not_finalized}),
        )
    logger.info(
        "Isolated finalization summary | sessions to create: {} | candidate sessions to delete: {}",
        len(sessions_to_create),
        len(candidate_session_ids_to_delete),
    )

    # Save sessionization run
    logger.info(
        "[sessionization] Starting DEFERRED transaction for saving sessionization results"
    )
    async with get_db_connection(
        start_transaction=True, transaction_type="DEFERRED"
    ) as conn:
        sessionization_run = SessionizationRun(
            candidate_creation_start=candidate_creation_interval_start,
            candidate_creation_end=candidate_creation_interval_end,
            finalized_horizon=finalized_horizon,
            overlap_start=overlap_start,
            right_tail_end=right_tail_end,
        )
        sessionization_id = await insert_sessionization_run(
            conn, sessionization_run=sessionization_run
        )

        if candidate_session_ids_to_delete:
            await delete_candidate_sessions_by_ids(
                conn, candidate_session_ids=candidate_session_ids_to_delete
            )

        if sessions_to_create:
            session_ids = await insert_sessions(
                conn,
                sessions=[spec.session for spec in sessions_to_create],
                sessionization_run_id=sessionization_id,
            )
            session_to_activities = []
            for spec, sid in zip(sessions_to_create, session_ids):
                for aid in spec.activity_ids:
                    session_to_activities.append(
                        SessionToActivity(session_id=sid, activity_id=aid)
                    )
            if session_to_activities:
                await insert_session_to_activity(conn, mappings=session_to_activities)

        await delete_candidate_sessions_without_activities(conn)


async def deal_with_island(
    island: Island,
    carry_over_candidate_session_specs: list[DBCandidateSessionSpec],
    window_end: datetime,
    min_activities_per_session: int,
    min_purity: float,
    min_session_length: timedelta,
    max_session_gap: timedelta,
    max_session_window_overlap: timedelta,
    llm_config: LLMConfig,
) -> RightConnectedIslandResult | RightIsolatedIslandResult:
    proposals = await propose_candidate_sessions_for_island(
        island=island.activity_specs,
        window_end=window_end,
        carry_over_session_specs=carry_over_candidate_session_specs,
        max_activities_per_session_llm_call=config.max_activities_per_session_llm_call,
        llm_config=llm_config,
    )

    island_activity_count = len(island.activity_specs)
    new_candidate_activity_count = sum(
        len(ids) for ids in proposals.new_mappings.values()
    )
    updated_candidate_activity_count = sum(
        len(ids) for ids in proposals.existing_mappings.values()
    )
    island_start_time = min(spec.start_time for spec in island.activity_specs)
    island_end_time = max(spec.end_time(window_end) for spec in island.activity_specs)
    logger.info(
        "Island {} -> {} | activities: {} | left_connected: {} | right_connected: {}",
        island_start_time,
        island_end_time,
        island_activity_count,
        island.left_connected,
        island.right_connected,
    )
    logger.info(
        "Island proposals | new sessions: {} ({} activities) | carry-over updates: {} ({} activities)",
        len(proposals.new_mappings),
        new_candidate_activity_count,
        len(proposals.existing_mappings),
        updated_candidate_activity_count,
    )

    if island.right_connected:
        # ---- Build combined specs (carry-over merged with new; plus brand-new) ----
        combined_specs: list[CandidateSessionSpec | DBCandidateSessionSpec] = []

        # 1) carry-overs with merged new mappings (keep DB* type to track deletions later)
        for db_spec in carry_over_candidate_session_specs:
            merged_ids = set(db_spec.activity_ids)
            merged_ids |= proposals.existing_mappings.get(db_spec.session, set())
            combined_specs.append(
                DBCandidateSessionSpec(
                    session=db_spec.session, activity_ids=sorted(merged_ids)
                )
            )

        # 2) brand-new candidate session specs from this island
        for sess, aids in proposals.new_mappings.items():
            combined_specs.append(
                CandidateSessionSpec(session=sess, activity_ids=sorted(aids))
            )

        # ---- Compute overlap cut (F) for this island ----

        island_start = min(spec.start_time for spec in island.activity_specs)
        island_span = window_end - island_start
        overlap_duration = min(max_session_window_overlap, island_span)
        overlap_start = window_end - overlap_duration  # CUT boundary (F)

        # ---- Finalize safe-left on the prefix (≤ F) if island long enough to have a tail ----
        if island_span > max_session_window_overlap:
            finalized = finalize_right_connected_island(
                island=island.activity_specs,
                island_end=window_end,
                candidate_specs=combined_specs,  # include carry-over + merged + new
                overlap_start=overlap_start,  # the CUT, not first-tail-start
                min_activities=min_activities_per_session,
                min_purity=min_purity,
                min_length=min_session_length,
                max_gap=max_session_gap,
            )
            finalized_horizon = finalized.finalized_horizon
            new_session_specs = finalized.session_specs_to_create
            activity_ids_to_delete_from_candidate_sessions = (
                finalized.activity_ids_to_delete_from_candidate_sessions
            )
        else:
            # Whole island is within overlap region → defer finalization
            new_session_specs = []
            finalized_horizon = island_start
            activity_ids_to_delete_from_candidate_sessions = []

        # ---- Tail-only candidates to persist (avoid carrying finalized left atoms) ----
        # Build fast lookup for activity end-times
        tail_cut = overlap_start
        tail_ids: set[int] = {
            s.activity.id
            for s in island.activity_specs
            if s.end_time(window_end) > tail_cut
        }

        # For new candidate sessions (those not in DB yet), keep only tail IDs
        tail_new_candidate_specs: list[CandidateSessionSpec] = []
        for sess, aids in proposals.new_mappings.items():
            tail_aids = sorted(a for a in aids if a in tail_ids)
            if tail_aids:
                tail_new_candidate_specs.append(
                    CandidateSessionSpec(session=sess, activity_ids=tail_aids)
                )

        # For existing DB candidates, keep only tail IDs for mapping inserts
        tail_existing_mappings: dict[DBCandidateSession, set[int]] = {}
        for db_sess, aids in proposals.existing_mappings.items():
            tail_aids = {a for a in aids if a in tail_ids}
            if tail_aids:
                tail_existing_mappings[db_sess] = tail_aids
        last_activity_end = max(sp.end_time(window_end) for sp in island.activity_specs)
        logger.info(
            "Right-connected island summary | finalized sessions: {} | tail candidates: {} | carry-over tail updates: {} | pruned candidate activities: {}",
            len(new_session_specs),
            len(tail_new_candidate_specs),
            sum(len(ids) for ids in tail_existing_mappings.values()),
            len(activity_ids_to_delete_from_candidate_sessions),
        )
        return RightConnectedIslandResult(
            new_candidate_session_specs=tail_new_candidate_specs,  # tail-only
            new_mappings_existing_candidate_sessions=tail_existing_mappings,  # tail-only
            session_specs_to_create=new_session_specs,
            finalized_horizon=finalized_horizon,
            overlap_start=overlap_start,  # record the CUT
            right_tail_end=last_activity_end,
            activity_ids_to_delete_from_candidate_sessions=activity_ids_to_delete_from_candidate_sessions,
        )

    # ---------- Right-isolated island: finalize everything now ----------
    candidate_session_specs: list[CandidateSessionSpec] = []
    for session, activity_ids in proposals.new_mappings.items():
        candidate_session_specs.append(
            CandidateSessionSpec(session=session, activity_ids=list(activity_ids))
        )
    for db_sess, aids in proposals.existing_mappings.items():
        candidate_session_specs.append(
            CandidateSessionSpec(
                session=CandidateSession(name=db_sess.name, llm_id=db_sess.llm_id),
                activity_ids=list(aids),
            )
        )

    result = validate_and_select_sessions(
        island=island.activity_specs,
        island_end=window_end,
        candidate_specs=candidate_session_specs,
        min_activities=min_activities_per_session,
        min_purity=min_purity,
        min_length=min_session_length,
        max_gap=max_session_gap,
    )

    candidate_session_ids_to_delete = [
        spec.session.id
        for spec in carry_over_candidate_session_specs
        if any(
            aid in spec.activity_ids
            for aid in (act.activity_id for act in island.activity_specs)
        )
    ]

    logger.info(
        "Right-isolated island summary | finalized sessions: {} | candidate sessions deleted: {}",
        len(result),
        len(candidate_session_ids_to_delete),
    )

    return RightIsolatedIslandResult(
        candidate_session_ids_to_delete=candidate_session_ids_to_delete,
        session_specs_to_create=result,
    )


async def run_sessionization():
    logger.info("Starting sessionization run")
    async with get_db_connection() as conn:
        user_settings = await select_user_settings(conn)
        if not user_settings:
            logger.warning("No user settings found. Exiting sessionization run.")
            return
        llm_config = user_settings.text_model_config
        previous_run = await select_latest_sessionization_run(conn)

        logger.info("Fetched previous sessionization run: {}", previous_run)

        latest_aggregation = await select_last_aggregation(conn)

        if not latest_aggregation:
            logger.warning("No aggregations found. Exiting sessionization run.")
            return
        latest_aggregation_interval_end_time = latest_aggregation.end_time
        carry_over_candidate_session_specs = await select_candidate_session_specs(conn)
        logger.info(
            f"Found carry over session specs: {carry_over_candidate_session_specs}"
        )
        logger.info(
            "Carry-over candidate sessions: {} | total mapped activities: {}",
            len(carry_over_candidate_session_specs),
            sum(len(spec.activity_ids) for spec in carry_over_candidate_session_specs),
        )

        if previous_run is None:
            candidate_creation_interval_end = latest_aggregation_interval_end_time
            candidate_creation_interval_start = (
                candidate_creation_interval_end - config.session_window_length
            )
        else:
            candidate_creation_interval_start = previous_run.candidate_creation_end
            # Debug timezone awareness and values before comparison to diagnose naive/aware mismatches
            start_plus_window = (
                candidate_creation_interval_start + config.session_window_length
            )
            logger.info(
                "Sessionization interval debug | prev_end: {} (tzinfo={} type={}) | +window: {} (tzinfo={} type={}) | latest_agg_end: {} (tzinfo={} type={})",
                candidate_creation_interval_start,
                getattr(candidate_creation_interval_start, "tzinfo", None),
                type(candidate_creation_interval_start),
                start_plus_window,
                getattr(start_plus_window, "tzinfo", None),
                type(start_plus_window),
                latest_aggregation_interval_end_time,
                getattr(latest_aggregation_interval_end_time, "tzinfo", None),
                type(latest_aggregation_interval_end_time),
            )
            candidate_creation_interval_end = min(
                start_plus_window,
                latest_aggregation_interval_end_time,
            )

            # If previous run already processed up to or beyond the latest aggregation,
            # skip sessionization until new data is aggregated
            if (
                candidate_creation_interval_start
                >= latest_aggregation_interval_end_time
            ):
                logger.info(
                    "No new data to process: previous run candidate_creation_end "
                    f"({candidate_creation_interval_start}) >= latest aggregation end "
                    f"({latest_aggregation_interval_end_time}). Skipping sessionization."
                )
                return

        if candidate_creation_interval_start > candidate_creation_interval_end:
            error_message = (
                f"Invalid candidate creation interval: start={candidate_creation_interval_start} "
                f">= end={candidate_creation_interval_end}"
                "Aborting sessionization run."
            )
            logger.error(error_message)
            return None

    # Fetch specs from previous window's overlap region FIRST (before early exit check)
    specs_not_finalized: list[DBActivitySpecWithTags] = []
    if previous_run and previous_run.overlap_start is not None:
        if previous_run.finalized_horizon is None:
            error_message = (
                "Inconsistent previous run: overlap_start is set but finalized_horizon is None. "
                "Aborting sessionization run."
            )
            logger.error(error_message)
            return None

        logger.info(
            "Fetching overlap activities from previous window: {} -> {}",
            previous_run.finalized_horizon,
            previous_run.candidate_creation_end,
        )
        async with get_db_connection() as conn:
            specs_not_finalized = await select_specs_with_tags_in_time_range(
                conn,
                start=previous_run.finalized_horizon,
                end=previous_run.candidate_creation_end,
            )
        logger.info(
            "Overlap region: {} -> {} | overlap activity specs: {} | unique activities: {}",
            previous_run.finalized_horizon,
            previous_run.candidate_creation_end,
            len(specs_not_finalized),
            len({spec.activity_id for spec in specs_not_finalized}),
        )
    else:
        logger.info(
            "No overlap region from previous window (first run or no unfinalized activities)"
        )

    # Fetch new activities in current window
    new_activity_specs = await select_specs_with_tags_in_time_range(
        conn,
        start=candidate_creation_interval_start,
        end=candidate_creation_interval_end,
    )

    logger.info(
        "Current window: {} -> {} | new activity specs: {} | unique activities: {}",
        candidate_creation_interval_start,
        candidate_creation_interval_end,
        len(new_activity_specs),
        len({spec.activity_id for spec in new_activity_specs}),
    )

    new_activity_specs_sorted = sorted(
        new_activity_specs,
        key=lambda spec: spec.end_time(horizon=candidate_creation_interval_end),
    )

    # EARLY EXIT: No new activities AND no overlap activities to process
    if not new_activity_specs_sorted and not specs_not_finalized:
        logger.info(
            "No activities to process (new activities: 0, overlap activities: 0) - early exit"
        )
        await finalize_carry_over_sessions_and_save(
            carry_over_candidate_session_specs=carry_over_candidate_session_specs,
            specs_not_finalized=specs_not_finalized,
            candidate_creation_interval_start=candidate_creation_interval_start,
            candidate_creation_interval_end=candidate_creation_interval_end,
            finalized_horizon=None,
            overlap_start=None,
            right_tail_end=None,
        )
        logger.info("Sessionization complete (no new or overlap activities)")
        return

    # EARLY EXIT: No new activities but overlap activities exist - process them
    if not new_activity_specs_sorted:
        logger.info(
            "No new activities in current window, but {} overlap activities need processing",
            len(specs_not_finalized),
        )
        await finalize_carry_over_sessions_and_save(
            carry_over_candidate_session_specs=carry_over_candidate_session_specs,
            specs_not_finalized=specs_not_finalized,
            candidate_creation_interval_start=candidate_creation_interval_start,
            candidate_creation_interval_end=candidate_creation_interval_end,
            finalized_horizon=None,
            overlap_start=None,
            right_tail_end=None,
        )
        logger.info(
            "Sessionization complete (processed {} overlap activities, no new activities)",
            len(specs_not_finalized),
        )
        return

    logger.info(
        "Processing sessionization | new activities: {} | overlap activities: {} | total to process: {}",
        len(new_activity_specs_sorted),
        len(specs_not_finalized),
        len(new_activity_specs_sorted) + len(specs_not_finalized),
    )

    # Extract islands from new activity specs
    islands = extract_valid_islands(
        specs_in_time_range=new_activity_specs_sorted,
        window_end=candidate_creation_interval_end,
        previous_window_last_active=previous_run.right_tail_end
        if previous_run
        else None,
        max_session_gap=config.max_session_gap,
        min_activities_per_session=config.min_activities_per_session,
        min_session_length=config.min_session_length,
    )

    logger.info(
        "Extracted {} islands | left-connected: {} | right-connected: {}",
        len(islands),
        sum(1 for island in islands if island.left_connected),
        sum(1 for island in islands if island.right_connected),
    )

    # EARLY EXIT: No valid islands - finalize isolated carry-over sessions and exit
    if not islands:
        logger.info("No valid islands found in current window")
        await finalize_carry_over_sessions_and_save(
            carry_over_candidate_session_specs=carry_over_candidate_session_specs,
            specs_not_finalized=specs_not_finalized,
            candidate_creation_interval_start=candidate_creation_interval_start,
            candidate_creation_interval_end=candidate_creation_interval_end,
            finalized_horizon=None,
            overlap_start=None,
            right_tail_end=None,
        )
        logger.info("Sessionization complete (no valid islands)")
        return

    # Initialize collections for sessions to create/delete
    sessions_to_create: list[SessionSpec] = []
    candidate_session_ids_to_delete: list[int] = []

    # Handle first island if it's NOT left-connected (isolated from previous window)
    if not islands[0].left_connected:
        logger.info(
            "First island is not left-connected, finalizing isolated previous window"
        )

        isolated_sessions, isolated_deletions = finalize_isolated_carry_over_sessions(
            carry_over_candidate_session_specs=carry_over_candidate_session_specs,
            specs_not_finalized=specs_not_finalized,
            candidate_creation_interval_end=candidate_creation_interval_end,
        )
        sessions_to_create.extend(isolated_sessions)
        candidate_session_ids_to_delete.extend(isolated_deletions)

    if islands:
        first_island = islands.pop(0)
        if first_island.left_connected:
            assert (
                previous_run is not None
            ), "previous_run must be set if first island is left_connected"

            assert (
                previous_run.finalized_horizon is not None
            ), "finalized_horizon must be set if first island is left_connected"
            overlap_specs = [
                x
                for x in specs_not_finalized
                if x.end_time(previous_run.candidate_creation_end)
                > previous_run.overlap_start  # type: ignore
            ]

            overlap_related_session_specs = [
                spec
                for spec in carry_over_candidate_session_specs
                if any(
                    activity_id in spec.activity_ids
                    for activity_id in (
                        activity_spec.activity_id for activity_spec in overlap_specs
                    )
                )
            ]

            first_island.activity_specs = list(
                set(first_island.activity_specs) | set(overlap_specs)
            )

        else:
            overlap_related_session_specs = []

        first_island_task = asyncio.create_task(
            deal_with_island(
                island=first_island,
                carry_over_candidate_session_specs=overlap_related_session_specs,
                window_end=candidate_creation_interval_end,
                min_activities_per_session=config.min_activities_per_session,
                min_purity=config.min_session_purity,
                min_session_length=config.min_session_length,
                max_session_gap=config.max_session_gap,
                max_session_window_overlap=config.max_session_window_overlap,
                llm_config=llm_config,
            )
        )

        island_tasks = [first_island_task]
        for island in islands:
            island_tasks.append(
                asyncio.create_task(
                    deal_with_island(
                        island=island,
                        carry_over_candidate_session_specs=[],
                        window_end=candidate_creation_interval_end,
                        min_activities_per_session=config.min_activities_per_session,
                        min_purity=config.min_session_purity,
                        min_session_length=config.min_session_length,
                        max_session_gap=config.max_session_gap,
                        max_session_window_overlap=config.max_session_window_overlap,
                        llm_config=llm_config,
                    )
                )
            )
    else:
        island_tasks = []

    candidate_session_specs_to_create: list[CandidateSessionSpec] = []
    new_mappings_existing_candidate_sessions: list[CandidateSessionToActivity] = []

    island_task_results = await asyncio.gather(*island_tasks)
    right_tail_end = None
    overlap_start = None
    finalized_horizon = None

    activity_ids_to_delete_from_candidate_sessions = []

    for r in island_task_results:
        match r:
            case RightConnectedIslandResult():
                right_tail_end = r.right_tail_end
                finalized_horizon = r.finalized_horizon
                overlap_start = r.overlap_start

                sessions_to_create.extend(r.session_specs_to_create)
                candidate_session_specs_to_create.extend(r.new_candidate_session_specs)
                for cid, aids in r.new_mappings_existing_candidate_sessions.items():
                    for aid in aids:
                        new_mappings_existing_candidate_sessions.append(
                            CandidateSessionToActivity(
                                candidate_session_id=cid.id, activity_id=aid
                            )
                        )
                activity_ids_to_delete_from_candidate_sessions.extend(
                    r.activity_ids_to_delete_from_candidate_sessions
                )

            case RightIsolatedIslandResult():
                sessions_to_create.extend(r.session_specs_to_create)
                candidate_session_ids_to_delete.extend(
                    r.candidate_session_ids_to_delete
                )

            case _:
                raise ValueError("Unexpected result from deal_with_island")

    logger.info(
        "[sessionization-isolated] Starting DEFERRED transaction for saving sessionization results"
    )
    async with get_db_connection(
        start_transaction=True, transaction_type="DEFERRED"
    ) as conn:
        sessionization_run = SessionizationRun(
            candidate_creation_start=candidate_creation_interval_start,
            candidate_creation_end=candidate_creation_interval_end,
            finalized_horizon=finalized_horizon,
            overlap_start=overlap_start,
            right_tail_end=right_tail_end,
        )

        sessionization_id = await insert_sessionization_run(
            conn, sessionization_run=sessionization_run
        )

        # Step 1: Delete candidate sessions (by ids)
        if candidate_session_ids_to_delete:
            await delete_candidate_sessions_by_ids(
                conn, candidate_session_ids=candidate_session_ids_to_delete
            )

        # Step 2: Delete candidate activity mappings (left-side finalized ids)
        if activity_ids_to_delete_from_candidate_sessions:
            await delete_candidate_session_to_activity_by_activity_ids(
                conn,
                activity_ids=activity_ids_to_delete_from_candidate_sessions,
            )

        # Step 3: Insert new candidate sessions and their mappings
        candidate_sessions_to_create = []
        candidate_session_mappings_to_create = []

        if candidate_session_specs_to_create:
            candidate_sessions_to_create = [
                x.session for x in candidate_session_specs_to_create
            ]

            candidate_session_ids = await insert_candidate_sessions(
                conn,
                sessions=candidate_sessions_to_create,
                sessionization_run_id=sessionization_id,
            )

            for spec, cid in zip(
                candidate_session_specs_to_create, candidate_session_ids
            ):
                for aid in spec.activity_ids:
                    candidate_session_mappings_to_create.append(
                        CandidateSessionToActivity(
                            candidate_session_id=cid, activity_id=aid
                        )
                    )

            await insert_candidate_session_to_activity(
                conn, mappings=candidate_session_mappings_to_create
            )

        logger.info(
            "Post-island summary | finalized sessions ready: {} | new candidate sessions: {} | existing candidate mappings: {} | candidate sessions to delete: {} | candidate activity ids to prune: {}",
            len(sessions_to_create),
            len(candidate_session_specs_to_create),
            len(new_mappings_existing_candidate_sessions),
            len(candidate_session_ids_to_delete),
            len(activity_ids_to_delete_from_candidate_sessions),
        )

        if (
            finalized_horizon is not None
            or overlap_start is not None
            or right_tail_end is not None
        ):
            logger.info(
                "Window markers | finalized_horizon: {} | overlap_start: {} | right_tail_end: {}",
                finalized_horizon,
                overlap_start,
                right_tail_end,
            )

        # Step 4: Insert mappings for existing candidates
        if new_mappings_existing_candidate_sessions:
            await insert_candidate_session_to_activity(
                conn, mappings=new_mappings_existing_candidate_sessions
            )

        # Step 5: Insert finalized sessions + session_to_activity
        if sessions_to_create:
            session_ids = await insert_sessions(
                conn,
                sessions=[spec.session for spec in sessions_to_create],
                sessionization_run_id=sessionization_id,
            )

            session_to_activities = []
            for spec, sid in zip(sessions_to_create, session_ids):
                for aid in spec.activity_ids:
                    session_to_activities.append(
                        SessionToActivity(session_id=sid, activity_id=aid)
                    )
            if session_to_activities:
                await insert_session_to_activity(conn, mappings=session_to_activities)

        # Step 6: Cleanup delete_candidate_sessions_without_activities
        await delete_candidate_sessions_without_activities(conn)

    logger.info("[sessionization-isolated] DEFERRED transaction committed successfully")
