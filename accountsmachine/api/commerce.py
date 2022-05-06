
import json
from aiohttp import web
import aiohttp
import glob
import logging
import uuid
from datetime import timezone
import math
import copy

from .. commerce.commerce import InvalidOrder

logger = logging.getLogger("api.commerce")
logger.setLevel(logging.DEBUG)

class CommerceApi():

    def __init__(self, config):
        pass

    async def get_offer(self, request):

        request["auth"].verify_scope("filing-config")
        user = request["auth"].user

        offer = await request["commerce"].get_offer(request["state"])

        return web.json_response(offer)

    async def get_balance(self, request):

        request["auth"].verify_scope("filing-config")
        user = request["auth"].user

        balance = await request["commerce"].get_balance(request["state"])

        return web.json_response(balance)

    async def create_order(self, request):

        request["auth"].verify_scope("filing-config")
        user = request["auth"].user
        email = request["auth"].email

        order = await request.json()

        try:
            tid = await request["commerce"].create_order(
                request["state"], order, user, email
            )
        except InvalidOrder as e:
            raise web.HTTPBadRequest(text=str(e))

        return web.json_response(tid)

    async def create_payment(self, request):

        request["auth"].verify_scope("filing-config")
        user = request["auth"].user

        secret = await request["commerce"].create_payment(
            request["state"], request.match_info["id"], user,
            request["auth"].email
        )

        return web.json_response(secret)

    async def complete_order(self, request):

        request["auth"].verify_scope("filing-config")
        id = request.match_info['id']

        await request["commerce"].complete_order(request["state"], id)

        return web.json_response()

    async def get_transactions(self, request):

        request["auth"].verify_scope("filing-config")

        try:
            ss = await request["commerce"].get_transactions(request["state"])

            for k in ss.keys():
                ss[k]["time"] = ss[k]["time"].astimezone(timezone.utc).replace(tzinfo=None).isoformat()

            return web.json_response(ss)
        except Exception as e:
            logger.debug("get_all: %s", e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def get_transaction(self, request):

        request["auth"].verify_scope("filing-config")
        id = request.match_info['id']

        try:
            tx = await request["commerce"].get_transaction(request["state"], id)
            tx["time"] = tx["time"].astimezone(timezone.utc).replace(tzinfo=None).isoformat()
            return web.json_response(tx)
        except Exception as e:
            logger.debug("get_all: %s", e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def get_payment_key(self, request):
        request["auth"].verify_scope("filing-config")

        key = await request["commerce"].get_payment_key(request["state"])

        return web.json_response({
            "key": key
        })

