

import base64
import logging

logger = logging.getLogger("audit.records")
logger.setLevel(logging.INFO)

class RecordObject:

    @staticmethod
    def transaction_record(tx):
        return {
            "time": tx["time"],
            "type": tx["type"],
            "uid": tx["uid"],
            "email": tx["email"],
            "transaction": tx,
        }

    def signup_record(time, uid, email, ref=None):
        rec = {
            "time": tx["time"],
            "type": "signup",
            "email": tx["email"],
            "uid": tx["uid"],
        }

        if ref: rec["ref"] = ref

        return rec

    def signup_record(time, uid, email, ref=None):
        rec = {
            "time": tx["time"],
            "type": "signup",
            "email": tx["email"],
            "uid": tx["uid"],
        }

        if ref: rec["ref"] = ref

        return rec

