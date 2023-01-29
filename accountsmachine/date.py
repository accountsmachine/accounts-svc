
from datetime import timezone

def to_isoformat(dt):
    return dt.astimezone(timezone.utc).replace(tzinfo=None).isoformat()


    
