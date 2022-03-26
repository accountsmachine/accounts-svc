
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
#     transaction: 'order',
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
                "description": "VAT return",
                "permitted": 10,
                "price": 650,
                "discount": 0.99,
                "min_purchase": 1,
            },
            "corptax": {
                "description": "Corporation tax filing",
                "permitted": 4,
                "price": 1450,
                "discount": 0.98,
                "min_purchase": 1,
            },
            "accounts": {
                "description": "Accounts filing",
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

        # If you already have the max, we can't sell you more.
        opts = {
            v: opts[v] for v in opts if opts[v]["permitted"] > 0
        }

        for kind in opts:

            res = opts[kind]

            offer = []

            for v in [0, *range(
                    res["min_purchase"], res["permitted"] + 1
            )]:
                price = math.floor(
                    purchase_price(
                        res["price"], v, res["discount"]
                    )
                )

                discount = (res["price"] * v) - price

                offer.append({
                    "price": price, "discount": discount, "quantity": v
                })

            res["offer"] = offer

        offer = {
            "offer": opts,
            "vat_rate": 0.2,
        }

        return web.json_response(offer)

    async def get_balance(self, request):

        request["auth"].verify_scope("filing-config")
        user = request["auth"].user

        balance = await request["state"].balance().get("balance")

        return web.json_response(balance)

    async def place_order(self, request):

        request["auth"].verify_scope("filing-config")
        user = request["auth"].user

        data = await request.json()

        # Need to verify everything from the client side.  Can't trust
        # any of it.

        balance = await request["state"].balance().get("balance")

        subtotal = 0

        for item in data["items"]:

            kind = item["kind"]
            count = item["quantity"]
            amount = item["amount"]

            resource = self.values[kind]

            if kind not in ["vat", "accounts", "corptax"]:
                raise web.HTTPBadRequest(text="Can't sell you one of those.")

            if kind not in balance["credits"]:
                balance["credits"][kind] = 0

            balance["credits"][kind] += count

            # The same resource could be listed multiple times, this works
            # for that case.

            if balance["credits"][kind] > resource["permitted"]:
                raise web.HTTPBadRequest(
                    text="That would exceed your maximum permitted"
                )

            price = math.floor(
                purchase_price(
                    resource["price"], count, resource["discount"]
                )
            )

            if amount != price:
                print(price, amount)
                raise web.HTTPBadRequest(
                    text="Wrong price"
                )

            subtotal += amount

        if subtotal != data["subtotal"]:
            raise web.HTTPBadRequest(text="Computed subtotal is wrong")

        # FIXME: Hard-coded VAT rate.
        # This avoids rounding errors.
        if abs(data["vat_rate"] - 0.2) > 0.00005:
            raise web.HTTPBadRequest(text="Tax rate is wrong")

        vat = round(subtotal * data["vat_rate"])

        if vat != data["vat"]:
            raise web.HTTPBadRequest(text="VAT calculation is wrong")

        total = subtotal + vat

        if total != data["total"]:
            raise web.HTTPBadRequest(text="Total calculation is wrong")

        # The order has been verified.

        transaction = {
            "transaction": "order",
            "address": [ "The Wirrals", "Lemlith", "Beaconsford" ],
            "billing_country": "UK", "country": "UK",
            "email": request["auth"].email,
            "time": datetime.datetime.now().isoformat(),
            "postcode": "BC1 9JJ", "name": "Mr. J. Smith",
            "uid": request["auth"].user, "valid": True,
            "vat_number": "GB123456789",
            "order": data
        }

        tid = str(uuid.uuid4())

        balance["time"] = datetime.datetime.now().isoformat()

        await request["state"].balance().put("balance", balance)
        await request["state"].transaction().put(tid, transaction)

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

