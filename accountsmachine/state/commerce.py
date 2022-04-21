
import asyncio
import json
import aiohttp
import glob
import logging
import uuid
import datetime
import math
import copy
from firebase_admin import firestore

import stripe
stripe.api_key = ""

logger = logging.getLogger("api.commerce")
logger.setLevel(logging.DEBUG)

class InvalidOrder(Exception):
    pass

# Accounts have a credit balance associated with them.  Credits are whole
# numbers.
# 
# The transaction collection has a list of transactions.  Purchase of
# credits:
#
# {
#     type: 'order',
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
#     kind: 'filing',
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
#     balance: 4,
# }

class Commerce:

    def __init__(self, config):

        stripe.api_key = config["stripe-secret"]
        self.stripe_public = config["stripe-public"] 
        self.seller_name = config["seller-name"] 
        self.seller_vat_number = config["seller-vat-number"]

        # 3 decimal places
        self.vat_rate = round(config["vat-rate"] / 100, 3)

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

    @staticmethod
    def purchase_price(base, units, discount=0.98):
        return base * units * (discount ** (units - 1))

    async def get_offer(self, user):

        balance = await self.get_balance(user)

        opts = copy.deepcopy(self.values)

        kinds = opts.keys()

        for kind in opts:
            if kind in balance:
                opts[kind]["permitted"] -= balance[kind]
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
                    Commerce.purchase_price(
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
            "vat_rate": self.vat_rate,
        }

        return offer

    async def get_balance(self, user):
        return await user.credits().get()

    # Validate order for internal integrity
    def verify_order(self, order):
        
        subtotal = 0

        for item in order["items"]:

            kind = item["kind"]
            count = item["quantity"]
            amount = item["amount"]

            if kind not in self.values:
                raise InvalidOrder(
                    text="We don't sell you one of those."
                )

            resource = self.values[kind]

            price = math.floor(
                Commerce.purchase_price(
                    resource["price"], count, resource["discount"]
                )
            )

            if amount != price:
                raise InvalidOrder(
                    text="Wrong price"
                )

            subtotal += amount

        if subtotal != order["subtotal"]:
            raise InvalidOrder(text="Computed subtotal is wrong")

        # This avoids rounding errors.
        if abs(order["vat_rate"] - self.vat_rate) > 0.00005:
            raise InvalidOrder(text="Tax rate is wrong")

        vat = round(subtotal * order["vat_rate"])

        if vat != order["vat"]:
            raise InvalidOrder(text="VAT calculation is wrong")

        total = subtotal + vat

        if total != order["total"]:
            raise InvalidOrder(text="Total calculation is wrong")

    # Returns potential new balance
    def get_order_delta(self, order):

        deltas = {}
        
        subtotal = 0

        for item in order["items"]:

            kind = item["kind"]
            count = item["quantity"]
            amount = item["amount"]

            if kind not in deltas:
                deltas[kind] = 0

            deltas[kind] += count

        return deltas

    async def create_tx(self, user, order, uid, email):

        profile = await user.get()

        transaction = {
            "type": "order",
            "name": profile["billing_name"],
            "address": profile["billing_address"],
            "city": profile["billing_city"],
            "county": profile["billing_county"],
            "country": profile["billing_country"],
            "postcode": profile["billing_postcode"],
            "email": profile["billing_email"],
            "tel": profile["billing_tel"],
            "seller_name": self.seller_name,
            "seller_vat_number": self.seller_vat_number,
            "time": datetime.datetime.now().isoformat(),
            "uid": uid, "complete": False,
            "status": "created",
            "vat_number": profile["billing_vat"],
            "order": order
        }

        return transaction

    async def create_order(self, user, order, uid, email):

        # Need to verify everything from the client side.  Can't trust
        # any of it.

        # First, check that the prices in the order are consistent with our
        # current offer, and that the calculations are internally consistent.
        self.verify_order(order)

        # This fetches the balance change from the order
        deltas = self.get_order_delta(order)

        newtx = await self.create_tx(user, order, uid, email)
        tid = str(uuid.uuid4())

        @firestore.async_transactional
        async def create_order(tx, deltas, newtx):

            bal = {}

            c = user.credits()
#            c.use_transaction(tx)
            bal = await c.get()

            for kind in deltas:

                if kind not in bal:
                    bal[kind] = 0

                permitted = self.values[kind]["permitted"]
                if bal[kind] + deltas[kind] > permitted:
                    return False, "That would exceed your maximum permitted"

            # Transaction gets written out, the new balance does not, as it
            # is not paid for yet.
            await user.transaction(tid).put(newtx)

            return True, "OK"

        tx = user.create_transaction()
        ok, msg = await create_order(tx, deltas, newtx)

        if not ok:
            raise RuntimeError(msg)

        return tid

    async def create_payment(self, user, tid, uid, email):

        transaction = await user.transaction(tid).get()
        order = transaction["order"]

        intent = stripe.PaymentIntent.create(
            amount=order["total"],
            currency='gbp',
            receipt_email=email,
            description="Accounts Machine credit purchase",
            metadata={
                "transaction": tid,
                "uid": uid,
            },
            automatic_payment_methods={ 'enabled': True },
        )

        transaction["payment_id"] = intent.id
        transaction["status"] = "pending"

        await user.transaction(tid).put(transaction)

        return intent["client_secret"]

    async def complete_order(self, user, id):

        intent = stripe.PaymentIntent.retrieve(id)
        tid = intent["metadata"]["transaction"]

        txdoc = user.transaction(tid)
        baldoc = user.credits()

        # Fetch transaction
        ordtx = await txdoc.get()
        ordtx["status"] = "complete"
        ordtx["complete"] = True

        # This works out the balance change from the order
        deltas = self.get_order_delta(ordtx["order"])

        @firestore.async_transactional
        async def update_order(tx, ordtx, deltas):

            c = baldoc
            # FIXME: Cause 409 error?!
#            c.use_transaction(tx)
            bal = await c.get()

            for kind in deltas:

                if kind not in bal:
                    bal[kind] = 0

                permitted = self.values[kind]["permitted"]
                if bal[kind] + deltas[kind] > permitted:
                    return False, "That would exceed your maximum permitted"

                bal[kind] += deltas[kind]

            await txdoc.put(ordtx)
            await baldoc.put(bal)
            return True, "OK"

        tx = user.create_transaction()
        ok, msg = await update_order(tx, ordtx, deltas)

        if not ok:
            raise RuntimeError(msg)

    async def get_transactions(self, user):

        ss = await user.transactions().list()
        return ss

    async def get_transaction(self, user, tid):
        try:
            tx = await user.transaction(tid).get()
            return tx
        except Exception as e:
            logger.debug("get_transaction: %s", e)
            return RuntimeError(
                body=str(e), content_type="text/plain"
            )

    async def get_payment_key(self, user):
        return self.stripe_public

