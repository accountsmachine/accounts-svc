#!/usr/bin/env python3

import json
import time
import asyncio

from aiohttp import web
import sys
import logging
import firebase_admin
from firebase_admin import credentials

from . store import Store
from . state import State
from . vat import Vat
from . render import Renderer
from . company import Company
from . auth import Auth
from . filing import Filing
from . books import Books
from . company_register import CompanyRegister
from . status import Status
from . corptax import Corptax
from . accounts import Accounts
from . firebase import Firebase
from . commerce import Commerce

logger = logging.getLogger("api")
logger.setLevel(logging.DEBUG)

class DataPass:

    @web.middleware
    async def add_data(self, request, handler):

        request["books"] = request.app["books"]

        if "auth" in request:

            # State provides a higher-level view, and knows the calling user
            request["state"] = State(request.app["store"], request["auth"].user)

        request["config"] = request.app["config"]
        request["renderer"] = request.app["renderer"]
        return await handler(request)

class Api:
    def __init__(self, config_file):

        self.config = json.loads(open(config_file).read())
        self.port = self.config["port"]

        self.firebase = Firebase(self.config)

        self.store = Store(self.config, self.firebase)
        self.auth = Auth(self.config, self.store, self.firebase)
        self.books = Books()
        self.company = Company()
        self.creg = CompanyRegister(self.config)
        self.filing = Filing()
        self.renderer = Renderer(self.config)
        self.accounts = Accounts()
        self.corptax = Corptax()
        self.vat = Vat(self.config, self.store)
        self.status = Status()
        self.commerce = Commerce(self.config)

        self.dp = DataPass()

        self.app = web.Application(middlewares=[self.auth.verify,
                                                self.dp.add_data])

        self.app["books"] = self.books
        self.app["store"] = self.store
        self.app["config"] = self.config
        self.app["renderer"] = self.renderer

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

        self.app.add_routes([web.get("/filings", self.filing.get_filings)])
        self.app.add_routes([web.get("/filing/{id}", self.filing.get_filing)])
        self.app.add_routes([web.put("/filing/{id}", self.filing.put_filing)])
        self.app.add_routes([web.delete("/filing/{id}",
                                        self.filing.delete_filing)])
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

        self.app.add_routes([web.get("/vat/liabilities/{id}",
                                     self.vat.get_liabilities)])
        self.app.add_routes([web.get("/vat/obligations/{id}",
                                     self.vat.get_obligations)])
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

        self.app.add_routes([web.get("/user-account/delete",
                                     self.auth.delete_user)])
        self.app.add_routes([web.post("/user-account/register",
                                     self.auth.register_user)])

        self.app.add_routes([web.get("/commerce/balance",
                                     self.commerce.get_balance)])
        self.app.add_routes([web.get("/commerce/offer",
                                     self.commerce.get_offer)])
        self.app.add_routes([web.get("/commerce/transactions",
                                     self.commerce.get_transactions)])
        self.app.add_routes([web.get("/commerce/transaction/{id}",
                                     self.commerce.get_transaction)])
        self.app.add_routes([web.post("/commerce/create-order",
                                      self.commerce.create_order)])
        self.app.add_routes([web.post("/commerce/complete-order/{id}",
                                      self.commerce.complete_order)])
        self.app.add_routes([web.post("/commerce/create-payment/{id}",
                                      self.commerce.create_payment)])
        self.app.add_routes([web.get("/commerce/payment-key",
                                      self.commerce.get_payment_key)])

    def run(self):

        web.run_app(self.app, port=self.port)

