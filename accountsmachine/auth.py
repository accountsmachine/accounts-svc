
from aiohttp import web
import secrets
import time
from urllib.parse import urlencode, quote_plus
import json
import hashlib
import logging
import asyncio
import uuid
import datetime

import firebase_admin
import firebase_admin.auth

from . state import State

logger = logging.getLogger("auth")
logger.setLevel(logging.DEBUG)

class RequestAuth:
    def __init__(self, user, scope, auth):
        self.auth = auth
        self.user = user
        self.scope = scope
    def verify_scope(self, scope):
        if scope not in self.scope:
            logger.debug("Scope forbidden: %s", scope)
            raise this.scope_invalid()
    def scope_invalid(self):
        return web.HTTPForbidden(
            text=json.dumps({
                "error_message": "You do not have permission",
                "code": "no-permission"
            }),
            content_type="application/json"
        )
    
class Auth:

    def __init__(self, config, store, firebase):

        self.store = store
        self.authreqs = {}
        self.firebase = firebase

        self.app_id = config["application-id"]
        self.audience = config["audience"]
        self.algorithms = config["algorithms"]

        try:
            self.domain = config["restrict-user-domain"]
        except:
            self.domain = None

    async def verify_auth(self, request):

        if "Authorization" not in request.headers:
            logger.debug("No auth header")
            raise self.auth_header_failure()

        toks = request.headers["Authorization"].split(" ")

        if len(toks) != 2:
            logger.debug("Bad auth header")
            raise self.auth_header_failure()

        if toks[0] != "Bearer":
            logger.debug("Bad auth header")
            raise self.auth_header_failure()

        # Verify JWT token
        try:
            auth = firebase_admin.auth.verify_id_token(toks[1])
        except:
            logger.debug("Token not valid")
            raise self.auth_header_failure()

        if (auth["exp"] <= time.time()):
            logger.debug("Token expired.")
            raise self.auth_header_failure()

        if not auth["email_verified"]:
            raise self.email_not_verified()
        
        if self.domain:
            email = auth["email"]
            if not email.endswith("@" + self.domain):
                raise self.auth_header_failure()

        # This shouldn't happen. I believe it's possible for an attacker
        # to use the Firebase API to create a user even though it's not in our
        # code, but they can't setup custom claims for the user.
        if "scope" not in auth:
            raise self.auth_header_failure()

        scope = auth["scope"]

        logger.debug("OK %s %s", auth["sub"], scope)

        a = RequestAuth(auth["sub"], scope, self)
        a.email = auth["email"]

        return a

    def email_not_verified(self):
        return web.HTTPUnauthorized(
            text=json.dumps({
                "error_message": "Email not verified",
                "code": "email-not-verified"
            }),
            content_type="application/json"
        )

    def auth_header_failure(self):
        return web.HTTPUnauthorized(
            text=json.dumps({
                "error_message": "Authorization not present",
                "code": "auth-not-present"
            }),
            content_type="application/json"
        )

    @web.middleware
    async def verify(self, request, handler):

        if request.url.path.startswith("/oauth"):
            return await handler(request)

        if request.url.path == "/user-account/register":
            return await handler(request)

        if request.url.path.startswith("/vat/receive-token"):
            return await handler(request)

        request["auth"] = await self.verify_auth(request)

        return await handler(request)


    async def register_user(self, request):

        try:

            user = await request.json()

            uid = str(uuid.uuid4())

            if "X-Application-ID" not in request.headers:
                raise HTTPUnauthorized()

            if request.headers["X-Application-ID"] != self.app_id:
                raise HTTPUnauthorized()

            # This is a new user.
            profile = {
                "version": "v1",
                "creation": datetime.datetime.utcnow().isoformat(),
                "email": user["email"],
            }

            scope = [
                "vat", "filing-config", "books", "company",
                "ch-lookup", "render", "status", "corptax",
                "accounts", "commerce", "user"
            ]

            # Initial balance
            # FIXME: uid is a managed by state.py
            balance = {
                "uid": uid,
                "time": datetime.datetime.utcnow().isoformat(),
                "email": user["email"],
                "credits": {
                    "vat": 0,
                    "corptax": 0,
                    "accounts": 0,
                }
            }

            state = State(self.store, uid)

            try:

                await state.user_profile().put(
                    uid, profile
                )

                await state.balance().put(
                    "balance", balance
                )

                firebase_admin.auth.create_user(
                    uid=uid, email=user["email"],
                    phone_number=user["phone_number"],
                    password=user["password"],
                    display_name=user["display_name"],
                    disabled=False
                )

                firebase_admin.auth.set_custom_user_claims(
                    uid, { "scope": scope, "application-id": self.app_id }
                )

                return web.Response()

            except Exception as e:

                # Tidy up, back-track
                try:
                    state.user_profile().delete(uid)
                except: pass

                try:
                    state.balance().delete(uid)
                except: pass

                try:
                    firebase_admin.auth.delete_user(uid)
                except: pass

                raise e

        except Exception as e:
            
            logger.debug("put: %s", e)

            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def delete_user(self, request):

        request["auth"].verify_scope("user")
        user = request["auth"].user

        try:

            return web.Response()

        except Exception as e:
            logger.debug("delete: %s", e)

            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )
