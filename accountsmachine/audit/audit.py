
import uuid
import base64
import logging
from datetime import datetime, timezone

from .. state import State

logger = logging.getLogger("audit.records")
logger.setLevel(logging.INFO)

class Audit:

    @staticmethod
    def transaction_record(tx):
        return {
            "time": tx["time"],
            "type": tx["type"],
            "uid": tx["uid"],
            "email": tx["email"],
            "transaction": tx,
        }

    @staticmethod
    def event_record(type, uid, email=None, ref=None):
        rec = {
            "time": datetime.now(timezone.utc),
            "type": type,
            "uid": uid,
        }

        if email: rec["email"] = email
        if ref: rec["ref"] = ref

        return rec

    @staticmethod
    async def write(store, rec, id=None):
        if id == None: id = str(uuid.uuid4())
        await State(store).log(id).put(rec)

