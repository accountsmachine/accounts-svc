
import asyncio
from aiohttp import web
from aiohttp import ClientSession
from urllib.parse import urlencode, quote_plus
import uuid
import secrets
import datetime
import json
import os
import logging
from io import StringIO
import requests
import re
import time

from .. state import State
from .. ixbrl_process import IxbrlProcess
from . render import RendererApi
from .. vat.vat import Vat, AuthNotConfigured, AccountsError

import gnucash_uk_vat.hmrc as hmrc
import gnucash_uk_vat.model as model
import gnucash_uk_vat.auth as auth

logger = logging.getLogger("api.vat")
logger.setLevel(logging.DEBUG)

def get_my_ip():

        # Cloud run services don't have a public IP
        return "0.0.0.0"

        # This works on normal machines
        import socket
        hostname = socket.gethostname()
        ip_address = socket.gethostbyname(hostname)
        return ip_address


class VatApi():
    def __init__(self, config, store):

        self.vat_auth_url = config["vat-auth-url"]
        self.vat_api_url = config["vat-api-url"]

        self.client_id = config["vat-client-id"]
        self.client_secret = config["vat-client-secret"]
        self.redirect_uri = config["redirect-uri"]

        self.store = store

        self.my_ip = get_my_ip()

        # FIXME: Lifecycle needs refactoring?  Doesn't belong here?
        self.renderer = RendererApi(config)

        self.vat = Vat(config, store)

    async def calculate(self, request):

        request["auth"].verify_scope("vat")
        user = request["auth"].user
        id = request.match_info['id']

        try:
            vat = await self.vat.calculate(request["state"], self.renderer, id)
        except AccountsError as e:
            return web.json_response(
                {
                    "error": {
                        "type": "account-error",
                        "account": e.account,
                        "message": e.message,
                    }
                }
            )

        return web.json_response(
            {
                "calculation": vat
            }
        )
                    
        
    async def compute(self, request):

        request["auth"].verify_scope("vat")
        user = request["auth"].user
        id = request.match_info['id']

        vat = await self.vat.compute(request["state"], self.renderer, id)

        return web.json_response(vat)
        
    async def redirect_auth(self, request):

        request["auth"].verify_scope("vat")
        state = request["state"]
        id = request.match_info['id']

        url = self.vat_auth_url + "/oauth/authorize?"

        secret = await self.vat.get_auth_ref(
                request["auth"].user, request["state"], id
        )

        url += urlencode({
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "state": secret,
            "scope": "read:vat write:vat",
            "client_id": self.client_id
        })

        return web.json_response({
            "url": url
        })

    async def receive_token(self, request):

        code = request.query["code"]
        state = request.query["state"]

        uid, company = await self.vat.receive_token(code, state)

        try:

            async with ClientSession() as session:

                req = urlencode({
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.redirect_uri,
                    "code": code,
                    "state": state,
                })

                headers = {
                        'Content-Type': 'application/x-www-form-urlencoded',
                }

                async with session.post(self.vat_api_url + "/oauth/token",
                                        headers=headers, data=req) as resp:
                    token = await resp.json()

        except Exception as e:
            logger.info("receive_token: Exception: %s", e)
            raise web.HTTPInternalServerError(
                body="Failed to exchange code for token",
                content_type="text/plain"
            )

        now = datetime.datetime.utcnow()
        expires = now + datetime.timedelta(seconds=int(token["expires_in"]))
        expires = expires.replace(microsecond=0)
        expires = expires.isoformat()

        token["expires"] = expires

        await self.vat.store_auth(uid, company, token)

        url = "/status/%s/vat" % company

        return web.HTTPFound(url)

    async def submit(self, request):

        request["auth"].verify_scope("vat")
        user = request["auth"].user
        id = request.match_info['id']
        config = self.get_vat_client_config(request)

        await self.vat.submit(
                user, request["auth"].email, config, request["state"],
                self.renderer, id
        )

        return web.json_response()

    def get_vat_client_config(self, request):

        user = request["auth"].user

        if "X-Device-ID" not in request.headers:
            raise RuntimeError("No device ID")

        if "X-Client-Version" not in request.headers:
            raise RuntimeError("No client version")

        if "X-Device-TZ" not in request.headers:
            raise RuntimeError("No timezone")

        peerinfo = request.transport.get_extra_info("peername")
        host, port = peerinfo[0], peerinfo[1]

        screen = json.loads(request.headers["X-Screen"])

        # The DNT header is deprecated
        dnt = "false"
        if "DNT" in request.headers and request.headers["DNT"] == "1":
                dnt = "true"

        # Get an parse X-Forwarded-For if it exists
        if "X-Forwarded-For" in request.headers:
            xff = request.headers["X-Forwarded-For"]
        elif "x-forwarded-for" in request.headers:
            xff = request.headers["x-forwarded-for"]
        else:
            xff = ""

        xff = xff.split(",")
        xff = [ v.strip() for v in xff ]
        xff = [v for v in filter(lambda x : x != "", xff)]

        return {
            "application.client-id": self.client_id,
            "application.client-secret": self.client_secret,
            "client.version": request.headers["X-Client-Version"],
            "transport.forwarded": xff,
#            "identity.vrn": "DUNNO",
            "identity.do-not-track": dnt,
            "identity.device.user-agent": request.headers["User-Agent"],
            "identity.device.id": request.headers["X-Device-ID"],
            "identity.device.tz": request.headers["X-Device-TZ"],
            "identity.transport.host": str(host),
            "identity.transport.port": str(port),
            "identity.user": request["auth"].user,
            "identity.email": request["auth"].email,
            "screen.width": screen[0],
            "screen.height": screen[1],
            "window.width": screen[2],
            "window.height": screen[3],
            "screen.colour-depth": screen[4],
            "screen.scaling-factor": screen[5],
            "server.ip": self.my_ip,
            "vat-auth-url": self.vat_auth_url,
            "vat-api-url": self.vat_api_url,
        }
    
    async def get_status(self, request):

        request["auth"].verify_scope("vat")
        state = request["state"]
        config = self.get_vat_client_config(request)

        try:

            id = request.match_info['id']
            start = request.query['start']
            end = request.query['end']

            start = datetime.date.fromisoformat(start)
            end = datetime.date.fromisoformat(end)

            status = await self.vat.get_status(config, state, id, start, end)

            return web.json_response(status)

        except AuthNotConfigured as e:
            return web.json_response({})

        except Exception as e:

            logger.debug("get_status: Exception: %s", e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def get_liabilities(self, request):

        request["auth"].verify_scope("vat")
        state = request["state"]
        config = self.get_vat_client_config(request)

        try:

            id = request.match_info['id']
            start = request.query['start']
            end = request.query['end']

            start = datetime.date.fromisoformat(start)
            end = datetime.date.fromisoformat(end)

            res = await self.vat.get_liabilities(config, state, id, start, end)

            return web.json_response(res)

        except Exception as e:

            logger.debug("get_status: Exception: %s", e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def get_obligations(self, request):

        request["auth"].verify_scope("vat")
        state = request["state"]
        config = self.get_vat_client_config(request)

        try:

            id = request.match_info['id']
            start = request.query['start']
            end = request.query['end']

            start = datetime.date.fromisoformat(start)
            end = datetime.date.fromisoformat(end)

            res = await self.vat.get_obligations(config, state, id, start, end)

            return web.json_response(res)

        except Exception as e:

            logger.debug("get_status: Exception: %s", e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def get_open_obligations(self, request):

        request["auth"].verify_scope("vat")
        state = request["state"]
        config = self.get_vat_client_config(request)

        try:

            id = request.match_info['id']

            res = await self.vat.get_open_obligations(config, state, id)

            return web.json_response(res)

        except Exception as e:

            logger.debug("get_status: Exception: %s", e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def get_payments(self, request):

        request["auth"].verify_scope("vat")
        state = request["state"]
        config = self.get_vat_client_config(request)

        try:

            id = request.match_info['id']
            start = request.query['start']
            end = request.query['end']

            start = datetime.date.fromisoformat(start)
            end = datetime.date.fromisoformat(end)

            res = await self.vat.get_payments(config, state, id, start, end)

            return web.json_response(res)

        except Exception as e:

            logger.debug("get_status: Exception: %s", e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def deauthorize(self, request):

        request["auth"].verify_scope("vat")
        user = request["state"]

        try:

            id = request.match_info['id']
            await user.company(id).vat_auth().delete()

            return web.Response()

        except Exception as e:

            logger.debug("deauthorize: Exception: %s", e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )
