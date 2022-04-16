
import datetime
import logging
import uuid

import firebase_admin
import firebase_admin.auth

from .. state import State

logger = logging.getLogger("admin.user")
logger.setLevel(logging.INFO)

class UserAdmin:
    def __init__(self, config, store):

        try:
            self.domain = config["restrict-user-domain"]
        except:
            self.domain = None

        self.store = store

    async def register_user(
            self, email, phone_number, display_name, password, app_id
    ):
        
        if self.domain:
            if not email.endswith("@" + self.domain):
                logger.info("User registered email with wrong domain")
                raise RuntimeError("Bad domain")

        uid = str(uuid.uuid4())

        # This is a new user.
        profile = {
            "version": "v1",
            "creation": datetime.datetime.utcnow().isoformat(),
            "email": email,
        }

        scope = [
            "vat", "filing-config", "books", "company",
            "ch-lookup", "render", "status", "corptax",
            "accounts", "commerce", "user"
        ]

        # Initial balance
        balance = {
            "time": datetime.datetime.utcnow().isoformat(),
            "email": email,
            "credits": {
                "vat": 0,
                "corptax": 0,
                "accounts": 0,
            }
        }

        state = State(self.store, uid)

        try:

            await state.user_profile().put(
                "profile", profile
            )

            await state.balance().put(
                "balance", balance
            )

            firebase_admin.auth.create_user(
                uid=uid, email=email,
                phone_number=phone_number,
                password=password,
                display_name=display_name,
                disabled=False
            )

            firebase_admin.auth.set_custom_user_claims(
                uid, { "scope": scope, "application-id": app_id }
            )

            return uid

        except Exception as e:

            # Need to attempt to back-track on all of the above setup
            logger.info("User create failed for %s", uid)

            # Tidy up, back-track
            try:
                await state.user_profile().delete("profile")
            except Exception as f:
                logger.info("Exception: %s", f)

            try:
                await state.balance().delete("balance")
            except Exception as f:
                logger.info("Exception: %s", f)
                
            try:
                firebase_admin.auth.delete_user(uid)
            except Exception as f:
                logger.info("Exception (delete_user): %s", f)

            raise e
