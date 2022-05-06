
import uuid
import base64
import logging
import datetime

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
    def event_record(type, uid, email=None):
        rec = {
            "time": datetime.datetime.utcnow().isoformat(),
            "type": type,
            "uid": uid,
        }

        if email: rec["email"] = email

        return rec

    @staticmethod
    def write(store, rec):
        State(store).record(str(uuid.uuid4())).put(rec)

