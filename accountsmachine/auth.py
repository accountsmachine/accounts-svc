
from aiohttp import web
import secrets
import jwt
import time
from urllib.parse import urlencode, quote_plus
import json
import hashlib
import logging
import asyncio

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

        self.jwt_secrets = config["jwt-secrets"]
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

        valid = False

        for sec in self.jwt_secrets:
            try:
                auth = jwt.decode(toks[1], sec,
                                  algorithms=self.algorithms,
                                  audience=self.audience)
                valid = True
                break
            except Exception as e:
                print(e)
                pass

        # FIXME: Permit none algorithm.  Insecure!!!
#        if not valid:
#            try:
#                auth = jwt.decode(toks[1], None, algorithms=["none"],
#                                  verify=False)
#                valid = True
#            except Exception as e:
#                pass

        if not valid:
            logger.debug("JWT not valid")
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

        if "scope" not in auth:

            # This is a new user.
            profile = {
                "version": "v1",
                "creation": int(time.time()),
                "email": auth["email"],
            }

            state = State(self.store, auth["sub"])

            cs = await state.user_profile().put(
                auth["sub"], profile
            )

            # set default scopes for user

            scope = [
                "vat", "filing-config", "books", "company",
                "ch-lookup", "render", "status", "corptax",
                "accounts"
            ]

            print(auth["sub"])

            logger.debug("Setting scopes for user not seen before")

            firebase_admin.auth.set_custom_user_claims(
                auth["sub"], { "scope": scope }
            )

        else:
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

        if request.url.path.startswith("/vat/receive-token"):
            return await handler(request)

        request["auth"] = await self.verify_auth(request)

        return await handler(request)
