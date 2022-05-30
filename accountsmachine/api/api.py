#!/usr/bin/env python3

import json
import time
import asyncio

from aiohttp import web
import sys
import logging
import firebase_admin
from firebase_admin import credentials

from .. state import Store, State
from .. firebase import Firebase

from . vat import VatApi
from . render import RendererApi
from . company import CompanyApi
from . auth import AuthApi
from . filing import FilingApi
from . books import BooksApi
from . company_register import CompanyRegisterApi
from . status import StatusApi
from . corptax import CorptaxApi
from . accounts import AccountsApi
from . commerce import CommerceApi
from .. commerce.commerce import Commerce

logger = logging.getLogger("api")
logger.setLevel(logging.DEBUG)

class DataPass:

    @web.middleware
    async def add_data(self, request, handler):

        if "auth" in request:

            # State provides a higher-level view, and knows the calling user
            request["state"] = State(
                request.app["store"]
            ).user(
                request["auth"].user
            )

        request["config"] = request.app["config"]
        request["renderer"] = request.app["renderer"]
        request["commerce"] = request.app["commerce"]
        request["store"] = request.app["store"]
        return await handler(request)

class Api:
    def __init__(self, config_file):

        self.config = json.loads(open(config_file).read())
        self.port = self.config["port"]

        self.firebase = Firebase(self.config)

        self.commerce = Commerce(self.config)

        self.store = Store(self.config)
        self.auth = AuthApi(self.config, self.store, self.firebase)
        self.books = BooksApi()
        self.company = CompanyApi()
        self.creg = CompanyRegisterApi(self.config)
        self.filing = FilingApi()
        self.renderer = RendererApi(self.config)
        self.accounts = AccountsApi()
        self.corptax = CorptaxApi()
        self.vat = VatApi(self.config, self.store)
        self.status = StatusApi()

        self.dp = DataPass()

        self.app = web.Application(middlewares=[self.auth.verify,
                                                self.dp.add_data])

        self.app["store"] = self.store
        self.app["config"] = self.config
        self.app["renderer"] = self.renderer
        self.app["commerce"] = self.commerce

        self.app.add_routes([web.post("/render-html/{id}",
                                      self.renderer.to_html)])

        self.app.add_routes([web.get("/companies", self.company.get_all)])
        self.app.add_routes([web.get("/company/{id}", self.company.get)])
        self.app.add_routes([web.put("/company/{id}", self.company.put)])
        self.app.add_routes([web.delete("/company/{id}", self.company.delete)])
        self.app.add_routes([web.post("/company/{id}/logo",
                                      self.company.upload_logo)])
        self.app.add_routes([web.get("/company/{id}/logo",
                                     self.company.get_logo)])

        self.app.add_routes([web.get("/filings", self.filing.get_all)])
        self.app.add_routes([web.get("/filing/{id}", self.filing.get)])
        self.app.add_routes([web.put("/filing/{id}", self.filing.put)])
        self.app.add_routes([web.delete("/filing/{id}",
                                        self.filing.delete)])
        self.app.add_routes([web.post("/filing/{id}/signature",
                                      self.filing.upload_signature)])
        self.app.add_routes([web.get("/filing/{id}/signature",
                                     self.filing.get_signature)])
        self.app.add_routes([web.get("/filing/{id}/report",
                                     self.filing.get_report)])
        self.app.add_routes([web.get("/filing/{id}/data",
                                     self.filing.get_data)])
        self.app.add_routes([web.get("/filing/{id}/status",
                                     self.filing.get_status)])
        self.app.add_routes([web.post("/filing/{id}/move-draft",
                                      self.filing.move_draft)])

        self.app.add_routes([web.post("/books/{id}/upload", self.books.upload)])
        self.app.add_routes([web.get("/books/{id}/info", self.books.get_info)])
        self.app.add_routes([web.get("/books/{id}/summary",
                                     self.books.get_summary)])
        self.app.add_routes([web.delete("/books/{id}", self.books.delete)])
        self.app.add_routes([web.get("/books", self.books.get_all)])
        self.app.add_routes([web.get("/books/{id}/mapping",
                                     self.books.get_mapping)])
        self.app.add_routes([web.put("/books/{id}/mapping",
                                     self.books.put_mapping)])

        self.app.add_routes([web.get("/vat/liabilities/{id}",
                                     self.vat.get_liabilities)])
        self.app.add_routes([web.get("/vat/obligations/{id}",
                                     self.vat.get_obligations)])
        self.app.add_routes([web.get("/vat/status/{id}",
                                     self.vat.get_status)])
        self.app.add_routes([web.get("/vat/open-obligations/{id}",
                                     self.vat.get_open_obligations)])
        self.app.add_routes([web.get("/vat/payments/{id}",
                                     self.vat.get_payments)])

        self.app.add_routes([web.post("/vat/compute/{id}", self.vat.compute)])
        self.app.add_routes([web.post("/vat/submit/{id}", self.vat.submit)])

        self.app.add_routes([web.post("/accounts/submit/{id}",
                                      self.accounts.submit)])

        self.app.add_routes([web.post("/corptax/submit/{id}",
                                      self.corptax.submit)])

        self.app.add_routes([web.get("/vat/receive-token",
                                     self.vat.receive_token)])
        self.app.add_routes([web.get("/vat/authorize/{id}",
                                     self.vat.redirect_auth)])
        self.app.add_routes([web.post("/vat/deauthorize/{id}",
                                      self.vat.deauthorize)])

        self.app.add_routes([web.post("/corptax/authorize/{id}",
                                      self.corptax.authorize)])
        self.app.add_routes([web.post("/corptax/deauthorize/{id}",
                                      self.corptax.deauthorize)])

        self.app.add_routes([web.post("/accounts/authorize/{id}",
                                      self.accounts.authorize)])
        self.app.add_routes([web.post("/accounts/deauthorize/{id}",
                                      self.accounts.deauthorize)])

        self.app.add_routes([web.get("/status", self.status.get_all)])
        self.app.add_routes([web.get("/status/{id}", self.status.get)])

        self.app.add_routes([web.get("/company-reg/{id}", self.creg.get)])

        self.app.add_routes([web.post("/user-account/delete",
                                     self.auth.delete_user)])
        self.app.add_routes([web.post("/user-account/register",
                                     self.auth.register_user)])
        self.app.add_routes([web.get("/user-account/profile",
                                     self.auth.get_profile)])
        self.app.add_routes([web.put("/user-account/profile",
                                     self.auth.put_profile)])

        commerce_api = CommerceApi(self.config)

        self.app.add_routes([web.get("/commerce/balance",
                                     commerce_api.get_balance)])
        self.app.add_routes([web.get("/commerce/offer",
                                     commerce_api.get_offer)])
        self.app.add_routes([web.get("/commerce/transactions",
                                     commerce_api.get_transactions)])
        self.app.add_routes([web.get("/commerce/transaction/{id}",
                                     commerce_api.get_transaction)])

        self.app.add_routes([web.get("/commerce/payment-key",
                                      commerce_api.get_payment_key)])
        self.app.add_routes([web.post("/commerce/create-order",
                                      commerce_api.create_order)])
        self.app.add_routes([web.post("/commerce/create-payment/{id}",
                                      commerce_api.create_payment)])
        self.app.add_routes([web.post("/commerce/complete-order/{id}",
                                      commerce_api.complete_order)])

        self.app.add_routes([web.get("/crypto/status",
                                     commerce_api.crypto_get_status)])
        self.app.add_routes([web.get("/crypto/currencies",
                                     commerce_api.crypto_get_currencies)])
        self.app.add_routes([web.post("/crypto/estimate",
                                      commerce_api.crypto_get_estimate)])
        self.app.add_routes([web.post("/crypto/payment",
                                      commerce_api.crypto_create_payment)])
        self.app.add_routes([web.get("/crypto/payment/{id}",
                                     commerce_api.crypto_get_payment_status)])
        self.app.add_routes([web.post("/crypto/callback/{user}/{id}",
                                     commerce_api.crypto_callback)])

    def run(self):

        web.run_app(self.app, port=self.port)

