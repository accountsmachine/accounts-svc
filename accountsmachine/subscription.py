
import json
from aiohttp import web
import aiohttp
import glob
import logging
import uuid
import datetime

logger = logging.getLogger("subscription")
logger.setLevel(logging.DEBUG)

class Subscription():

    def __init__(self, config):
        pass

    async def get_all(self, request):

        request["auth"].verify_scope("filing-config")
        user = request["auth"].user

        try:
            ss = await request["state"].subscription().list()

            # There's nothing which expires subscriptions, so we have
            # to do it on load.

            now = datetime.datetime.utcnow()

            for id in ss:
                subs = ss[id]

                exp = datetime.datetime.fromisoformat(subs["expires"])

                # Expire, write back to DB
                if subs["valid"] and exp < now:
                    subs["valid"] = False
                    subs["status"] = "expired"
                    await request["state"].subscription().put(id, subs)

            return web.json_response(ss)

        except Exception as e:
            logger.debug("get_all: %s", e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def get(self, request):

        request["auth"].verify_scope("filing-config")
        user = request["auth"].user

        try:

            id = request.match_info['id']

            if ".." in id:
                raise RuntimeError("Invalid id")

            data = await request["state"].subscription().get(id)

            now = datetime.datetime.utcnow()

            if data["valid"] and exp < now:
                subs["valid"] = False
                subs["status"] = "expired"
                await request["state"].subscription().put(id, data)

            return web.json_response(data)

        except Exception as e:
            logger.debug("get: %s", e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def take(self, request):

        request["auth"].verify_scope("filing-config")

        user = request["auth"].user

        try:

            cmp = request.match_info['company']
            kind = request.match_info['kind']

            if ".." in cmp:
                raise RuntimeError("Invalid id")

            if ".." in kind:
                raise RuntimeError("Invalid id")

            id = str(uuid.uuid4())

            start = datetime.datetime.utcnow()
            end = start.replace(year=start.year + 1)

            provides = []

            if kind.startswith("vat-"):
                provides = ["vat"]
            elif kind.startswith("all-"):
                provides = ["vat", "corptax", "accounts"]

            subs = {
                "company": cmp,
                "uid": user,
                "email": request["auth"].email,
                "kind": kind,
                "opened": start.isoformat(),
                "expires": end.isoformat(),
                "purchaser": "Mr. J. Smith",
                "address": [
                    "The Wirrals", "Lemlith", "Beaconsford"
                ],
                "postcode": "BC1 9JJ",
                "country": "UK",
                "valid": True,
                "billing_country": "UK",
                "vat_rate": 20,
                "vat_number": "GB123456789",
                "provides": provides,
            }

            await request["state"].subscription().put(id, subs)

            return web.json_response(id)

        except Exception as e:
            logger.debug("get: %s", e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

