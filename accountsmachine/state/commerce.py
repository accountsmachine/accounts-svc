
import json
import aiohttp
import glob
import logging
import uuid
import datetime
import math
import copy

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

class Commerce:

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

    @staticmethod
    def purchase_price(base, units, discount=0.98):
        return base * units * (discount ** (units - 1))

    async def get_offer(self, state):

        balance = await state.balance().get("balance")

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
            "vat_rate": 0.2,
        }

        return offer

    async def get_balance(self, state):

        return await state.balance().get("balance")

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
                raise InvalidOrder(
                    text="We don't sell you one of those."
                )

            if kind not in balance["credits"]:
                balance["credits"][kind] = 0

            balance["credits"][kind] += count

            # The same resource could be listed multiple times, this works
            # for that case.

            if balance["credits"][kind] > resource["permitted"]:
                raise InvalidOrder(
                    text="That would exceed your maximum permitted"
                )

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

        # FIXME: Hard-coded VAT rate.
        # This avoids rounding errors.
        if abs(order["vat_rate"] - 0.2) > 0.00005:
            raise InvalidOrder(text="Tax rate is wrong")

        vat = round(subtotal * order["vat_rate"])

        if vat != order["vat"]:
            raise InvalidOrder(text="VAT calculation is wrong")

        total = subtotal + vat

        if total != order["total"]:
            raise InvalidOrder(text="Total calculation is wrong")

        return balance

    async def create_tx(self, state, order, user, email):

        profile = await state.user_profile().get("profile")
        print(profile)

        transaction = {
            "transaction": "order",
            "name": profile["billing_name"],
            "address": profile["billing_address"],
            "city": profile["billing_city"],
            "county": profile["billing_county"],
            "country": profile["billing_country"],
            "postcode": profile["billing_postcode"],
            "email": profile["billing_email"],
            "tel": profile["billing_tel"],
            "time": datetime.datetime.now().isoformat(),
            "uid": user, "complete": False,
            "status": "pending",
            "vat_number": profile["billing_vat"],
            "order": order
        }

        return transaction

    async def create_order(self, state, order, user, email):

        balance = await state.balance().get("balance")

        # Need to verify everything from the client side.  Can't trust
        # any of it.
        balance = self.verify_order(order, balance)

        transaction = await self.create_tx(state, order, user, email)

        tid = str(uuid.uuid4())

        await state.transaction().put(tid, transaction)

        return tid

    async def create_payment(self, state, tid, user, email):

        transaction = await state.transaction().get(tid)
        order = transaction["order"]

        intent = stripe.PaymentIntent.create(
            amount=order["total"],
            currency='gbp',
            receipt_email=email,
            description="Accounts Machine credit purchase",
            metadata={
                "transaction": tid,
                "uid": user,
            },
            automatic_payment_methods={ 'enabled': True },
        )

        transaction["payment_id"] = intent.id

        await state.transaction().put(tid, transaction)

        return intent["client_secret"]

    async def complete_order(self, state, id):

        intent = stripe.PaymentIntent.retrieve(id)
        tid = intent["metadata"]["transaction"]

        balance = await state.balance().get("balance")
        transaction = await state.transaction().get(tid)

        # Don't need to validate the order, but this returns the new
        # balance.
        balance = self.verify_order(transaction["order"], balance)

        transaction["status"] = "complete"
        transaction["complete"] = True

        await state.balance().put("balance", balance)
        await state.transaction().put(tid, transaction)

        return balance

    async def get_transactions(self, state):

        ss = await state.transaction().list()
        return ss

    async def get_transaction(self, state, id):
        try:
            tx = await state.transaction().get(id)
            return tx
        except Exception as e:
            logger.debug("get_all: %s", e)
            return RuntimeError(
                body=str(e), content_type="text/plain"
            )

    async def get_payment_key(self, state):
        return self.stripe_public

