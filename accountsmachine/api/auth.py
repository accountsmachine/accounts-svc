
from aiohttp import web
import json
import logging
import copy
from datetime import datetime

from .. admin.user import UserAdmin, EmailNotVerified, AuthHeaderFailure, BadDomain
from .. date import to_isoformat

logger = logging.getLogger("api.auth")
logger.setLevel(logging.INFO)

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
            authr = await self.user_admin.verify_token(toks[1])
        except EmailNotVerified:
            raise self.email_not_verified()
        except AuthHeaderFailure:
            raise self.auth_header_failure()
        except BadDomain:
            raise self.bad_domain()

        return authr

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

        if request.url.path.startswith("/crypto/callback"):
            return await handler(request)

        if request.url.path.startswith("/commerce/callback"):
            return await handler(request)

        request["auth"] = await self.verify_auth(request)

        return await handler(request)


    async def register_user(self, request):

        try:

            user = await request.json()

            if "X-Application-ID" not in request.headers:
                return web.HTTPUnauthorized()

            # App-id isn't a feature which is used, currently, it's here in
            # case we want to do API as a service later.
            if request.headers["X-Application-ID"] != self.app_id:
                return web.HTTPUnauthorized()

            try:
                ref = user["ref"]
            except:
                ref = None

            # Security feature: Passing parameters by name, because don't want
            # to accidentally put password in the wrong field.
            uid = await self.user_admin.register_user(
                email=user["email"], phone_number=user["phone_number"],
                display_name=user["display_name"], password=user["password"],
                app_id=self.app_id, ref=ref,
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

            await self.user_admin.delete_user(request["state"], user)
            return web.Response()

        except Exception as e:
            logger.debug("delete_user: %s", e)

            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def get_profile(self, request):

        request["auth"].verify_scope("user")

        prof = await self.user_admin.get_profile(request["state"])

        prof["creation"] = to_isoformat(prof["creation"])

        return web.json_response(prof)

    async def put_profile(self, request):

        request["auth"].verify_scope("user")

        user = request["auth"].user

        prof = await self.user_admin.get_profile(request["state"])

        info = await request.json()

        info["creation"] = datetime.fromisoformat(prof["creation"])

        await self.user_admin.put_profile(request["state"], info)

        return web.json_response()

