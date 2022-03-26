
import json
from aiohttp import web
import aiohttp
import glob
import logging
import uuid
import datetime
import math
import copy

logger = logging.getLogger("commerce")
logger.setLevel(logging.DEBUG)

def purchase_price(base, units, discount=0.98):
    return base * units * (discount ** (units - 1))

# Accounts have a credit balance associated with them.  Credits are whole
# numbers.
# 
# The transaction collection has a list of transactions.  Purchase of
# credits:
#
# {
#     transaction: 'buy',
#     address: [ "The Wirrals", "Lemlith", "Beaconsford" ],
#     billing_country: "UK", country: "UK", email: "mark@accountsmachine.io",
#     kind: "vat", time: "2022-03-24T11:03:57.411167",
#     postcode: "BC1 9JJ", name: "Mr. J. Smith",
#     uid: "ROElfkN481YZAxmO6U6eMzvmXGt2", valid: true,
#     vat_number: "GB123456789", vat_rate: 20
#     credits: 10, price: 14.84,
# }
#
# Consumption:
# {
#     kind: 'use',
#     company: "12874000", resource: "vat", filing: "fkN481YZAx",
#     credits: -1, time: "2022-03-24T11:03:57.411167",
#     uid: "ROElfkN481YZAxmO6U6eMzvmXGt2", email:  "mark@accountsmachine.io"
# }
#
# Transaction status for purchases can be 'pending', 'applied', 'rejected'
# Transaction status for consumptions can be 'applied', 'complete', 'removed'
#
# Balance:
# {
#     uid: "ROElfkN481YZAxmO6U6eMzvmXGt2",
#     time: "2022-03-24T11:03:57.41116",
#     email: "mark@accountsmachine.io",
#     credits: {
#         vat: 0,
#         accounts: 0,
#         corptax: 0,
#     }
# }

class Commerce():

    def __init__(self, config):

        self.values = {
            "vat": {
                "permitted": 10,
                "price": 650,
                "discount": 0.99,
                "min_purchase": 1,
            },
            "corptax": {
                "permitted": 4,
                "price": 1450,
                "discount": 0.98,
                "min_purchase": 1,
            },
            "accounts": {
                "permitted": 4,
                "price": 950,
                "discount": 0.98,
                "min_purchase": 1,
            }
        }

    async def get_offer(self, request):

        request["auth"].verify_scope("filing-config")
        user = request["auth"].user

        balance = await request["state"].balance().get("balance")

        opts = copy.deepcopy(self.values)

        kinds = opts.keys()

        for kind in opts:
            if kind in balance["credits"]:
                opts[kind]["permitted"] -= balance["credits"][kind]
                opts[kind]["permitted"] = max(opts[kind]["permitted"], 0)

        for kind in opts:
            res = opts[kind]
            res["offer"] = [
                {
                    "credits": v,
                    "price": math.floor(
                        purchase_price(
                            res["price"], v, res["discount"]
                        )
                    )
                }
                for v in [0, *range(
                        res["min_purchase"], res["permitted"] + 1
                )]
            ]

        opts["vat_tax_rate"] = 0.2

        return web.json_response(opts)

    async def get_balance(self, request):

        request["auth"].verify_scope("filing-config")
        user = request["auth"].user

        balance = await request["state"].balance().get("balance")

        return web.json_response(balance)

    async def purchase(self, request):

        request["auth"].verify_scope("filing-config")
        user = request["auth"].user

        kind = request.match_info['kind']
        data = await request.json()

        count = data["count"]

        if kind not in ["vat", "accounts", "corptax"]:
            raise web.HTTPBadRequest()

        # FIXME Should be a transaction

        values = self.values[kind]

        price = purchase_price(values["price"], count, values["discount"])

        # Get my balance
        balance = request["state"].balance().get("balance")
        if balance["credit"][kind] + count > values["permitted"]:
            return web.HTTPBadRequest("This exceeds your maximum permitted")

        if count < values["min_purchase"]:
            return web.HTTPBadRequest("This exceeds your minimum purchase")

        transaction = {
            "transaction": "buy",
            "address": [ "The Wirrals", "Lemlith", "Beaconsford" ],
            "billing_country": "UK", "country": "UK",
            "email": request["auth"].email,
            "kind": kind, "time": datetime.datetime.now().isoformat(),
            "postcode": "BC1 9JJ", "name": "Mr. J. Smith",
            "uid": request["auth"].user, "valid": True,
            "vat_number": "GB123456789", "vat_rate": 20,
            "credits": count, "price": price,
        }

        tid = str(uuid.uuid4())
        balance["credits"][kind] += count
        balance["time"] = datetime.datetime.now().isoformat()

        request["state"].balance().put("balance", balance)
        request["state"].transaction().put(tid, transaction)

        return web.json_response(balance)
    
    async def get_transactions(self, request):

        request["auth"].verify_scope("filing-config")
        user = request["auth"].user

        try:
            ss = await request["state"].transaction().list()

            return web.json_response(ss)

        except Exception as e:
            logger.debug("get_all: %s", e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )
