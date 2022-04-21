
import json
from aiohttp import web
import aiohttp
import glob
import logging

from .. state import Company

logger = logging.getLogger("api.status")
logger.setLevel(logging.DEBUG)

class StatusApi():

    def __init__(self):
        pass

    async def get_all(self, request):

        request["auth"].verify_scope("status")
        user = request["state"]

        comps = await Company.get_all(request["state"])

        resp = {}

        for cid in comps:

            vat = True
            try:
                comp = await user.company(cid).vat_auth().get()
            except:
                vat = False

            corptax = True
            try:
                comp = await user.company(cid).corptax_auth().get()
            except:
                corptax = False

            accounts = True
            try:
                comp = await user.company(cid).accounts_auth().get()
            except:
                accounts = False

            resp[cid] = {
                "vat": vat,
                "corptax": corptax,
                "accounts": accounts,
            }

        return web.json_response(resp)

    async def get(self, request):

        request["auth"].verify_scope("status")
        user = request["state"]

        cid = request.match_info['id']

        vat = True
        try:
            comp = await user.company(cid).vat_auth().get()
        except:
            vat = False

        corptax = True
        try:
            comp = await user.company(cid).corptax_auth().get()
        except:
            corptax = False

        accounts = True
        try:
            comp = await user.company(cid).accounts_auth().get()
        except:
            accounts = False

        resp = {
            "vat": vat,
            "corptax": corptax,
            "accounts": accounts,
        }

        return web.json_response(resp)

