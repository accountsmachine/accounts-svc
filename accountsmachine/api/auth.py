
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

from .. state import State
from .. admin.user import UserAdmin

logger = logging.getLogger("api.auth")
logger.setLevel(logging.INFO)

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
    
class AuthApi:

    def __init__(self, config, store, firebase):

        self.store = store
        self.authreqs = {}

        self.app_id = config["application-id"]
        self.audience = config["audience"]
        self.algorithms = config["algorithms"]

        self.user_admin = UserAdmin(config, store)

    async def verify_auth(self, request):

        if "Authorization" not in request.headers:
            logger.debug("No auth header")
            raise self.auth_header_failure()

        toks = request.headers["Authorization"].split(" ")

        if len(toks) != 2:
            logger.info("Bad auth header")
            raise self.auth_header_failure()

        if toks[0] != "Bearer":
            logger.info("Bad auth header")
            raise self.auth_header_failure()

        # Verify JWT token
        try:
            auth = firebase_admin.auth.verify_id_token(toks[1])
        except:
            logger.info("Token not valid")
            raise self.auth_header_failure()

        if (auth["exp"] <= time.time()):
            logger.info("Token expired.")
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
                "message": "Email not verified",
                "code": "email-not-verified"
            }),
            content_type="application/json"
        )

    def auth_header_failure(self):
        return web.HTTPUnauthorized(
            text=json.dumps({
                "message": "Authorization not present",
                "code": "auth-not-present"
            }),
            content_type="application/json"
        )

    def bad_domain(self):
        return web.HTTPUnauthorized(
            text=json.dumps({
                "message":
                "Your email address is not in an authorised domain",
                "code": "auth-wrong-domain"
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
                return HTTPUnauthorized()

            # App-id isn't a feature which is used, currently, it's here in
            # case we want to do API as a service later.
            if request.headers["X-Application-ID"] != self.app_id:
                return HTTPUnauthorized()

            # Security feature: Passing parameters by name, because don't want
            # to accidentally put password in the wrong field.
            uid = await self.user_admin.register_user(
                email=user["email"], phone_number=user["phone_number"],
                display_name=user["display_name"], password=user["password"],
                app_id=self.app_id
            )

            return web.Response()

        except Exception as e:
            
            logger.info("register_user: %s", e)

            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def delete_user(self, request):

        request["auth"].verify_scope("user")
        user = request["auth"].user

        try:

            # FIXME: Not implemented.
            return web.Response()

        except Exception as e:
            logger.debug("delete_user: %s", e)

            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )
