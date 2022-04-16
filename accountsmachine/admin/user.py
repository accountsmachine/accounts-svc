
import datetime
import logging
import uuid
import time

import firebase_admin
import firebase_admin.auth

from .. state import State

logger = logging.getLogger("admin.user")
logger.setLevel(logging.INFO)

class AuthHeaderFailure(Exception):
    pass

class EmailNotVerified(Exception):
    pass

class BadDomain(Exception):
    pass

class RequestAuth:
    def __init__(self, user, scope, auth):
        self.auth = auth
        self.user = user
        self.scope = scope
    def verify_scope(self, scope):
        if scope not in self.scope:
            logger.info("Scope forbidden: %s", scope)
            raise this.scope_invalid()
    def scope_invalid(self):
        return web.HTTPForbidden(
            text=json.dumps({
                "message": "You do not have permission",
                "code": "no-permission"
            }),
            content_type="application/json"
        )
    
class UserAdmin:
    def __init__(self, config, store):

        try:
            self.domain = config["restrict-user-domain"]
        except:
            self.domain = None

        self.store = store

    async def delete_user(self, user):

        raise RuntimeError("Not implemented")

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

    async def verify_token(self, token):
        
        try:
            # Annoying - not async?
            # FIXME: Not async
            auth = firebase_admin.auth.verify_id_token(token)
        except:
            logger.info("Token not valid")
            raise AuthHeaderFailure()

        if (auth["exp"] <= time.time()):
            logger.info("Token expired.")
            raise AuthHeaderFailure()

        if not auth["email_verified"]:
            raise EmailNotVerified()
        
        if self.domain:
            email = auth["email"]
            if not email.endswith("@" + self.domain):
                raise BadDomain()

        # This shouldn't happen. I believe it's possible for an attacker
        # to use the Firebase API to create a user even though it's not in our
        # code, but they can't setup custom claims for the user.
        if "scope" not in auth:
            raise AuthHeaderFailure()

        scope = auth["scope"]

        logger.info("OK %s %s", auth["sub"], scope)

        a = RequestAuth(auth["sub"], scope, self)
        a.email = auth["email"]

        return a
