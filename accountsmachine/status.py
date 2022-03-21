
import json
from aiohttp import web
import aiohttp
import glob

class Status():

    def __init__(self):
        pass

    async def get_all(self, request):

        request["auth"].verify_scope("status")
        user = request["auth"].user

        comps = await request["state"].company().list()

        resp = {}

        for cid in comps:

            vat = True
            try:
                comp = await request["state"].vat_auth().get(cid)
            except:
                vat = False

            corptax = True
            try:
                comp = await request["state"].corptax_auth().get(cid)
            except:
                corptax = False

            accounts = True
            try:
                comp = await request["state"].accounts_auth().get(cid)
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
        user = request["auth"].user

        cid = request.match_info['id']

        vat = True
        try:
            comp = await request["state"].vat_auth().get(cid)
        except:
            vat = False

        corptax = True
        try:
            comp = await request["state"].corptax_auth().get(cid)
        except:
            corptax = False

        accounts = True
        try:
            comp = await request["state"].accounts_auth().get(cid)
        except:
            accounts = False

        resp = {
            "vat": vat,
            "corptax": corptax,
            "accounts": accounts,
        }

        return web.json_response(resp)

