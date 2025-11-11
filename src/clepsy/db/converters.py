from datetime import datetime, timezone


def convert_date(x: bytes | None):
    if x is None:
        return None
    date_str = x.decode()
    return datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
