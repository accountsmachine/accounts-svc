
import asyncio
import json
import aiohttp
import glob
import logging
import uuid
from datetime import datetime, timezone
from urllib.parse import urlencode, quote_plus
import math
import copy
from firebase_admin import firestore

from .. admin.referral import Package
from .. audit.audit import Audit

import stripe
stripe.api_key = ""

logger = logging.getLogger("api.commerce")
logger.setLevel(logging.DEBUG)

logging.getLogger("stripe").setLevel(logging.INFO)

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

        self.nowpayments_key = config["nowpayments-api-key"]
        self.nowpayments_url = config["nowpayments-url"]

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
                "description": "Corp. tax filing",
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
        package = await user.currentpackage().get()
        package = Package.from_dict(package)

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

        package_discount = None

        if package:
            if package.expiry > datetime.now(timezone.utc):
                if package.discount:
                    package_discount = package.discount

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

                if package_discount and getattr(package_discount, kind):
                    adj = round(price * getattr(package_discount, kind))
                    discount += adj
                    price -= adj

                offer.append({
                    "price": price, "discount": discount, "quantity": v
                })

            res["offer"] = offer

            if package_discount and getattr(package_discount, kind):
                discp = str(int(100 * getattr(package_discount, kind))) + "%"
                res["adjustment"] = package.id + " " + discp

        offer = {
            "offer": opts,
            "vat_rate": self.vat_rate,
        }

        return offer

    async def get_balance(self, user):
        return await user.credits().get()

    # Validate order for internal integrity
    def verify_order(self, order, package):

        pkg_discount = None
        if package:
            if package.expiry > datetime.now(timezone.utc):
                if package.discount:
                    pkg_discount = package.discount
        
        subtotal = 0

        for item in order["items"]:

            kind = item["kind"]
            count = item["quantity"]
            amount = item["amount"]
            disc = item["discount"]

            if kind not in self.values:
                raise InvalidOrder("We don't sell you one of those.")

            resource = self.values[kind]

            price = math.floor(
                Commerce.purchase_price(
                    resource["price"], count, resource["discount"]
                )
            )

            discount = (resource["price"] * count) - price

            adj = 0
            if pkg_discount:
                if getattr(pkg_discount, kind):
                    adj = round(getattr(pkg_discount, kind) * price)
                    price -= adj
                    discount += adj

            if amount != price:
                raise InvalidOrder("Wrong price")

            if disc != discount:
                raise InvalidOrder("Wrong discount")

            subtotal += amount

        if subtotal != order["subtotal"]:
            raise InvalidOrder("Computed subtotal is wrong")

        # This avoids rounding errors.
        if abs(order["vat_rate"] - self.vat_rate) > 0.00005:
            raise InvalidOrder("Tax rate is wrong")

        vat = round(subtotal * order["vat_rate"])

        if vat != order["vat"]:
            raise InvalidOrder("VAT calculation is wrong")

        total = subtotal + vat

        if total != order["total"]:
            raise InvalidOrder("Total calculation is wrong")

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
            "time": datetime.now(timezone.utc),
            "uid": uid, "complete": False,
            "status": "created",
            "vat_number": profile["billing_vat"],
            "order": order
        }

        return transaction

    async def create_order(self, user, order, uid, email):

        # Need to verify everything from the client side.  Can't trust
        # any of it.

        # Get user package
        package = await user.currentpackage().get()
        package = Package.from_dict(package)

        # First, check that the prices in the order are consistent with our
        # current offer, and that the calculations are internally consistent.
        self.verify_order(order, package)

        # This fetches the balance change from the order
        deltas = self.get_order_delta(order)

        newtx = await self.create_tx(user, order, uid, email)
        tid = str(uuid.uuid4())

        @firestore.async_transactional
        async def create_order(tx, deltas, newtx):

            bal = {}

            c = user.credits()
            c.use_transaction(tx)
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

        rec = Audit.transaction_record(newtx)
        await Audit.write(user.store, rec, id=tid)

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

        rec = Audit.transaction_record(transaction)
        await Audit.write(user.store, rec, id=tid)

        return intent["client_secret"]

    async def complete_order(self, user, id):

        # Card has been charged, this transaction really should not fail.
        # FIXME: Webhook would be a better way to achieve this.

        intent = stripe.PaymentIntent.retrieve(id)
        tid = intent["metadata"]["transaction"]

        # Fetch transaction outside of the transaction
        ordtxdoc = user.transaction(tid)
        ordtx = await ordtxdoc.get()

        ordtx["status"] = "complete"
        ordtx["complete"] = True

        # This works out the balance change from the order
        deltas = self.get_order_delta(ordtx["order"])

        # FIXME: Get 409 Too much contention when doing this transactionally
        # FIXME: Get 409 error, this SHOULD be done in the transaction
        cdoc = user.credits()
#        cdoc.use_transaction(tx)
        bal = await cdoc.get()

        for kind in deltas:
            if kind not in bal:
                bal[kind] = 0
            bal[kind] += deltas[kind]

        @firestore.async_transactional
        async def update_order(tx):

            await user.transaction(tid).put(ordtx)
            await user.credits().put(bal)

        tx = user.create_transaction()
        await update_order(tx)

        rec = Audit.transaction_record(ordtx)
        await Audit.write(user.store, rec, id=tid)

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

    async def crypto_get_status(self, user):

        async with aiohttp.ClientSession() as session:

            url = self.nowpayments_url + "v1/status"

            async with session.get(url) as resp:

                if resp.status != 200:
                    raise RuntimeError("Couldn't get status")

                ci = await resp.json()

            return ci

    async def crypto_get_currencies(self, user):

        async with aiohttp.ClientSession() as session:

            url = self.nowpayments_url + "v1/currencies"

            headers = {
                "x-api-key": self.nowpayments_key,
            }

            async with session.get(url, headers=headers) as resp:

                if resp.status != 200:
                    raise RuntimeError("Currency fetch failed")

                ci = await resp.json()

            return ci

    async def crypto_get_estimate(self, user, currency, order):

        # Get user package
        package = await user.currentpackage().get()
        package = Package.from_dict(package)

        self.verify_order(order, package)

        # Convert pence to pounds
        amount = order["total"] / 100

        async with aiohttp.ClientSession() as session:

            url = self.nowpayments_url + "v1/estimate?%s" % urlencode({
                "amount": amount,
                "currency_from": "gbp",
                "currency_to": currency
            })

            headers = {
                "x-api-key": self.nowpayments_key,
            }

            async with session.get(url, headers=headers) as resp:

                res = await resp.json()

                if resp.status == 400:
                    if "code" in res:
                        if res["code"] == "INVALID_REQUEST_PARAMS":
                            raise InvalidOrder(res["message"])

                if resp.status != 200:
                    raise RuntimeError("Currency fetch failed")

            return res

    async def crypto_create_payment(self, user, order, uid, email):

        request["auth"].verify_scope("filing-config")

        order = await request.json()

        # Get user package
        package = await user.currentpackage().get()
        package = Package.from_dict(package)

        self.verify_order(order, package)

        

    async def crypto_get_payment_status(self, request):
        request["auth"].verify_scope("filing-config")
        status = await request["commerce"].get_payment_status(request["state"])
        return web.json_response(status)

