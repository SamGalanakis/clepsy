from __future__ import annotations

from rq.cron import register

from clepsy.config import config
from clepsy.jobs.aggregation import aggregate_window
from clepsy.jobs.sessions import run_sessionization_job


# Base periodic jobs configured for RQ Cron. Run with:
#   rq cron clepsy.cron_config --url "$VALKEY_URL"

# Sessionization every configured window length
register(
    run_sessionization_job,
    queue_name="default",
    interval=int(config.session_window_length.total_seconds()),
)

# Aggregation tick: compute current window each run
register(
    aggregate_window,
    queue_name="aggregation",
    interval=int(config.aggregation_interval.total_seconds()),
)
