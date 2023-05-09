
from datetime import timezone
from datetime import datetime

def to_isoformat(dt):

    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)

    return dt.astimezone(timezone.utc).replace(tzinfo=None).isoformat()

