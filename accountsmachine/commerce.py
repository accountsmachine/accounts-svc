
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
#     kind: 'credit-purchase',
#     address: [ "The Wirrals", "Lemlith", "Beaconsford" ],
#     billing_country: "UK", country: "UK", email: "mark@accountsmachine.io",
#     resource: "vat", time: "2022-03-24T11:03:57.411167",
#     postcode: "BC1 9JJ", name: "Mr. J. Smith",
#     uid: "ROElfkN481YZAxmO6U6eMzvmXGt2", valid: true,
#     vat_number: "GB123456789", vat_rate: 20
#     credits: 10, price: 14.84,
# }
#
# Consumption:
# {
#     kind: 'credit-spend',
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
        pass

        self.available = [
            {
                "kind": "vat-6-month",
                "provides": ["vat"],
                "cost": 15,
                "period": [6, "month"],
                "horizon": [18, "month"],
            },
            {
                "kind": "vat-1-year",
                "provides": ["vat"],
                "cost": 20,
                "period": [1, "year"],
                "horizon": [18, "month"],
            },
            {
                "kind": "vat-2-year",
                "provides": ["vat"],
                "cost": 35,
                "period": [2, "year"],
                "horizon": [30, "month"],
            },
            {
                "kind": "accounts-1-year",
                "provides": ["accounts"],
                "cost": 15,
                "period": [1, "year"],
                "horizon": [18, "month"],
            },
            {
                "kind": "accounts-2-year",
                "provides": ["accounts"],
                "cost": 28,
                "period": [2, "year"],
                "horizon": [30, "month"],
            },
            {
                "kind": "corptax-1-year",
                "provides": ["corptax"],
                "cost": 20,
                "period": [1, "year"],
                "horizon": [18, "month"],
            },
            {
                "kind": "corptax-2-year",
                "provides": ["corptax"],
                "cost": 38,
                "period": [2, "year"],
                "horizon": [30, "month"],
            },
            {
                "kind": "all-1-year",
                "provides": ["corptax"],
                "cost": 40,
                "period": [1, "year"],
                "horizon": [18, "month"],
            },
            {
                "kind": "all-2-year",
                "provides": ["corptax"],
                "cost": 70,
                "period": [2, "year"],
                "horizon": [30, "month"],
            }
        ]

    async def get_all(self, request):

        request["auth"].verify_scope("filing-config")
        user = request["auth"].user

        try:
            ss = await request["state"].subscription().list()

            # There's nothing which expires subscriptions, so we have
            # to do it on load.

            now = datetime.datetime.utcnow()

            for id in ss:
                subs = ss[id]

                exp = datetime.datetime.fromisoformat(subs["expires"])

                # Expire, write back to DB
                if subs["valid"] and exp < now:
                    subs["valid"] = False
                    subs["status"] = "expired"
                    await request["state"].subscription().put(id, subs)

            return web.json_response(ss)

        except Exception as e:
            logger.debug("get_all: %s", e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def get(self, request):

        request["auth"].verify_scope("filing-config")
        user = request["auth"].user

        try:

            id = request.match_info['id']

            if ".." in id:
                raise RuntimeError("Invalid id")

            data = await request["state"].subscription().get(id)

            now = datetime.datetime.utcnow()

            if data["valid"] and exp < now:
                subs["valid"] = False
                subs["status"] = "expired"
                await request["state"].subscription().put(id, data)

            return web.json_response(data)

        except Exception as e:
            logger.debug("get: %s", e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def take(self, request):

        request["auth"].verify_scope("filing-config")

        user = request["auth"].user

        try:

            cmp = request.match_info['company']
            kind = request.match_info['kind']

            if ".." in cmp:
                raise RuntimeError("Invalid id")

            if ".." in kind:
                raise RuntimeError("Invalid id")

            id = str(uuid.uuid4())

            subs = self.configure_subscription(
                kind, cmp, request["auth"].email
            )

            await request["state"].subscription().put(id, subs)

            return web.json_response(id)

        except Exception as e:
            logger.debug("get: %s", e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def configure_subscription(kind, company, email):

        start = datetime.datetime.utcnow()
        end = start.replace(year=start.year + 1)

        provides = []

        if kind.startswith("vat-"):
            provides = ["vat"]
        elif kind.startswith("all-"):
            provides = ["vat", "corptax", "accounts"]

        subs = {
            "company": company,
            "uid": user,
            "email": email,
            "kind": kind,
            "opened": start.isoformat(),
            "expires": end.isoformat(),
            "purchaser": "Mr. J. Smith",
            "address": [
                "The Wirrals", "Lemlith", "Beaconsford"
            ],
            "postcode": "BC1 9JJ",
            "country": "UK",
            "valid": True,
            "billing_country": "UK",
            "vat_rate": 20,
            "vat_number": "GB123456789",
            "provides": provides,
        }

        return subs

    async def get_options(self, request):

        request["auth"].verify_scope("filing-config")
        user = request["auth"].user

        try:

            company = request.match_info['company']

            if ".." in company:
                raise RuntimeError("Invalid id")

            ss = await request["state"].subscription().list()

            now = datetime.datetime.utcnow()

            # Expire
            for id in ss:
                subs = ss[id]

                exp = datetime.datetime.fromisoformat(subs["expires"])

                # Expire, write back to DB
                if subs["valid"] and exp < now:
                    subs["valid"] = False
                    subs["status"] = "expired"
                    await request["state"].subscription().put(id, subs)

            # Just subscriptions for this company
            ss = [ss[k] for k in ss if ss[k]["company"] == company]
            ss = [v for v in ss if v["valid"]]

            options = self.compute_options(ss)

            return web.json_response(options)

        except Exception as e:
            logger.debug("get: %s", e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    def future(self, now, count, item):

        if item == "month":
            return now.add(datetime.datetime.timedelta(months=count))

        if item == "year":
            return now.add(datetime.datetime.timedelta(year=count))

        raise RuntimeError("BROKEN")

    # Find all options
    # - Look for extensions on all the current features
    # - Look for extensions on individual current features
    # - Offer the 'all' package.

    def compute_options(self, current):

        avail = {
            "vat": [],
            "corptax": [],
            "accounts": [],
            "all": []
        }

        for a in self.available:
            if a["provides"] == ["vat"]:
                avail["vat"].append(a)
            if a["provides"] == ["corptax"]:
                avail["vat"].append(a)
            if a["provides"] == ["accounts"]:
                avail["vat"].append(a)
            if set(a["provides"]) == set(["vat", "corptax", "accounts"]):
                avail["all"].append(a)

        print(">>>>>", avail)

        provided = set()
        for sub in current:
            provided |= set(sub["provides"])

        

#        print([v for v in powerset(provided)])

        return []

