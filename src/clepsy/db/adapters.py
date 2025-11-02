from datetime import datetime

from clepsy import utils


def adapt_timestamp(x: datetime) -> str:
    return utils.datetime_to_iso_8601(x)
