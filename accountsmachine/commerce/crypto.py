
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

from . product import product, purchase_price
from . exceptions import InvalidOrder

logger = logging.getLogger("api.crypto")
logger.setLevel(logging.DEBUG)

class Crypto:

    def __init__(self, config):

        self.seller_name = config["seller-name"] 
        self.seller_vat_number = config["seller-vat-number"]

        self.nowpayments_key = config["nowpayments-api-key"]
        self.nowpayments_url = config["nowpayments-url"]
        self.nowpayments_ipn_url = config["nowpayments-ipn-url"]

        # 3 decimal places
        self.vat_rate = round(config["vat-rate"] / 100, 3)

        self.values = product

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
                purchase_price(
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

    async def get_currencies(self, user):

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

    async def get_minimum(self, user, currency):

        async with aiohttp.ClientSession() as session:

            url = self.nowpayments_url + "v1/min-amount?%s" % urlencode({
                "currency_from": currency,
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

            return res["min_amount"]

    async def get_estimate(self, user, currency, order):

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

    async def create_tx(self, user, order, uid, email, cur):

        profile = await user.get()

        transaction = {
            "type": "order",
            "payment": "crypto",
            "payment_processor": "nowpayments.io",
            "payment_currency": cur,
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

    async def create_payment(self, user, currency, order, uid, email):

        # Get user package
        package = await user.currentpackage().get()
        package = Package.from_dict(package)

        self.verify_order(order, package)

        # Convert pence to pounds
        amount = order["total"] / 100

        newtx = await self.create_tx(user, order, uid, email, currency)
        tid = str(uuid.uuid4())

        rec = Audit.transaction_record(newtx)
        await Audit.write(user.store, rec, id=tid)

        await user.transaction(tid).put(newtx)

        async with aiohttp.ClientSession() as session:

            url = self.nowpayments_url + "v1/payment"

            ipn_url = self.nowpayments_ipn_url + "/" + uid + "/" + tid

            data = {
                "price_amount": amount,
                "price_currency": "gbp",
                "pay_currency": currency,
                "ipn_callback_url": ipn_url,
                "order_id": tid,
                "order_description": "accountsmachine.io filing credits",
                # Used for sandbox only
#                "case": "success",
#                "case": "failed",
#                "case": "partially_paid",
            }

            headers = {
                "x-api-key": self.nowpayments_key,
            }

            async with session.post(url, data=data, headers=headers) as resp:

                res = await resp.json()

                print(resp.status)

                if resp.status == 400:
                    if "code" in res:
                        if res["code"] == "INVALID_REQUEST_PARAMS":
                            raise InvalidOrder(res["message"])
                        if res["code"] == "AMOUNT_MINIMAL_ERROR":
                            raise InvalidOrder(res["message"])
                    if "message" in res:
                        raise InvalidOrder(res["message"])

                if resp.status != 201:
                    print(json.dumps(res, indent=4))
                    raise RuntimeError("Order creation failed")

            return res

    async def get_payment_status(self, user, id):

        async with aiohttp.ClientSession() as session:

            url = self.nowpayments_url + "v1/payment/%s" % id

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
                    raise RuntimeError("Payment fetch failed")

        return res

    async def callback(self, user, paym):

        tid = paym["order_id"]
        tx = await user.transaction(tid).get()

        tx["payment_amount"] = paym["pay_amount"]
        tx["payment_status"] = paym["payment_status"]

        # Complete the transaction if appropriate
        if tx["status"] == "created":
            tx["status"] = "pending"
            tx["payment_id"] = str(paym["payment_id"])

        if tx["status"] != "complete" and paym["payment_status"] == "finished":

            tx["status"] = "complete"
            deltas = self.get_order_delta(tx["order"])
            
            cdoc = user.credits()
            bal = await cdoc.get()

            for kind in deltas:
                if kind not in bal:
                    bal[kind] = 0
                bal[kind] += deltas[kind]

            await cdoc.put(bal)

        if tx["status"] != "failed" and paym["payment_status"] == "failed":
            tx["status"] = "failed"

        await user.transaction(tid).put(tx)

        rec = Audit.transaction_record(tx)
        await Audit.write(user.store, rec, id=tid)
