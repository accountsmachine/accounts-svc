
import json
from aiohttp import web
import aiohttp
import glob
import logging
import uuid
import datetime
import math
import copy

import stripe
stripe.api_key = ""

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
#     uid: "ROElfkN481YZAxmO6U6eMzvmXGt2", status: "complete", complete: true,
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

        stripe.api_key = config["stripe-secret"]

        self.stripe_public = config["stripe-public"] 

        self.values = {
            "vat": {
                "description": "VAT return",
                "permitted": 10,
                "price": 650,
                "discount": 0.995,
                "min_purchase": 1,
            },
            "corptax": {
                "description": "Corporation tax filing",
                "permitted": 4,
                "price": 1450,
                "discount": 0.995,
                "min_purchase": 1,
            },
            "accounts": {
                "description": "Accounts filing",
                "permitted": 4,
                "price": 950,
                "discount": 0.995,
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

    # Returns potential new balance
    def verify_order(self, order, balance):

        balance = copy.deepcopy(balance)
        
        subtotal = 0

        for item in order["items"]:

            kind = item["kind"]
            count = item["quantity"]
            amount = item["amount"]

            resource = self.values[kind]

            if kind not in ["vat", "accounts", "corptax"]:
                raise web.HTTPBadRequest(
                    text="We don't sell you one of those."
                )

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
                raise web.HTTPBadRequest(
                    text="Wrong price"
                )

            subtotal += amount

        if subtotal != order["subtotal"]:
            raise web.HTTPBadRequest(text="Computed subtotal is wrong")

        # FIXME: Hard-coded VAT rate.
        # This avoids rounding errors.
        if abs(order["vat_rate"] - 0.2) > 0.00005:
            raise web.HTTPBadRequest(text="Tax rate is wrong")

        vat = round(subtotal * order["vat_rate"])

        if vat != order["vat"]:
            raise web.HTTPBadRequest(text="VAT calculation is wrong")

        total = subtotal + vat

        if total != order["total"]:
            raise web.HTTPBadRequest(text="Total calculation is wrong")

        return balance

    def create_tx(self, request, order):

        transaction = {
            "transaction": "order",
            "address": [ "The Wirrals", "Lemlith", "Beaconsford" ],
            "billing_country": "UK", "country": "UK",
            "email": request["auth"].email,
            "time": datetime.datetime.now().isoformat(),
            "postcode": "BC1 9JJ", "name": "Mr. J. Smith",
            "uid": request["auth"].user, "complete": False,
            "status": "pending",
            "vat_number": "GB123456789",
            "order": order
        }

        return transaction

    async def create_order(self, request):

        request["auth"].verify_scope("filing-config")
        user = request["auth"].user

        balance = await request["state"].balance().get("balance")

        order = await request.json()

        # Need to verify everything from the client side.  Can't trust
        # any of it.
        balance = self.verify_order(order, balance)

        transaction = self.create_tx(request, order)

        tid = str(uuid.uuid4())

        await request["state"].transaction().put(tid, transaction)

        return web.json_response(tid)

    async def create_payment(self, request):

        request["auth"].verify_scope("filing-config")
        user = request["auth"].user

        tid = request.match_info['id']
        transaction = await request["state"].transaction().get(tid)
        order = transaction["order"]

        intent = stripe.PaymentIntent.create(
            amount=order["total"],
            currency='gbp',
            receipt_email=request["auth"].email,
            description="Accounts Machine credit purchase",
            metadata={
                "transaction": tid,
                "uid": request["auth"].user,
            },
            automatic_payment_methods={ 'enabled': True },
        )

        transaction["payment_id"] = intent.id

        await request["state"].transaction().put(tid, transaction)

        return web.json_response(intent["client_secret"])

    async def complete_order(self, request):

        request["auth"].verify_scope("filing-config")
        user = request["auth"].user

        data = await request.json()
        id = request.match_info['id']

        intent = stripe.PaymentIntent.retrieve(id)

        tid = intent["metadata"]["transaction"]

        balance = await request["state"].balance().get("balance")
        transaction = await request["state"].transaction().get(tid)

        # Don't need to validate the order, but this returns the new
        # balance.
        balance = self.verify_order(transaction["order"], balance)

        transaction["status"] = "complete"
        transaction["complete"] = True

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

    async def get_transaction(self, request):

        request["auth"].verify_scope("filing-config")
        user = request["auth"].user

        try:
            id = request.match_info['id']

            tx = await request["state"].transaction().get(id)

            return web.json_response(tx)

        except Exception as e:
            logger.debug("get_all: %s", e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def get_payment_key(self, request):

        request["auth"].verify_scope("filing-config")
        user = request["auth"].user

        return web.json_response({
            "key": self.stripe_public
        })

