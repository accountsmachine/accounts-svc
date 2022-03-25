
import json
from aiohttp import web
import aiohttp
import glob
import logging
import uuid
import datetime

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
                "max-hoarding": 10,
                "price": 6.50,
                "discount": 0.99,
                "min-purchase": 1,
            },
            "corptax": {
                "max-hoarding": 10,
                "price": 6.50,
                "discount": 0.99,
                "min-purchase": 1,
            },
            "accounts": {
                "max-hoarding": 10,
                "price": 6.50,
                "discount": 0.99,
                "min-purchase": 1,
            }
        }

    async def get_options(self, request):

        request["auth"].verify_scope("filing-config")
        user = request["auth"].user

        return web.json_response(self.values)

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
        if balance["credit"][kind] + count > values["max-hoarding"]:
            return web.HTTPBadRequest("This exceeds your maximum hoarding")

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
