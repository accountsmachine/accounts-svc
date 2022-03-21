#!/usr/bin/env python3

import json
import time
import asyncio
from aiohttp import web
import sys
import logging

from accountsmachine.store import Store
from state import State

from vat import Vat
from render import Renderer
from company import Company
from auth import Auth
from filing import Filing
from books import Books
from company_register import CompanyRegister
from status import Status
from corptax import Corptax
from accounts import Accounts

if len(sys.argv) != 2:
    print("Usage:\n\tengine <config>")
    sys.exit(1)

try:
    config = open(sys.argv[1]).read()
    config = json.loads(config)
except Exception as e:
    print("Error loading config: ", e)
    sys.exit(1)

logging.basicConfig(level=logging.DEBUG)

store = Store(config)

auth = Auth(config, store)

books = Books()
company = Company()
creg = CompanyRegister()
filing = Filing()
renderer = Renderer(config)
accounts = Accounts()
corptax = Corptax()
vat = Vat(config, store)
status = Status()

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

dp = DataPass()

app = web.Application(middlewares=[auth.verify, dp.add_data])

app["books"] = books
app["store"] = store
app["config"] = config
app["renderer"] = renderer

app.add_routes([web.post('/render-html/{id}', renderer.to_html)])

app.add_routes([web.get('/companies', company.get_all)])
app.add_routes([web.get('/company/{id}', company.get)])
app.add_routes([web.put('/company/{id}', company.put)])
app.add_routes([web.delete('/company/{id}', company.delete)])
app.add_routes([web.post('/company/{id}/logo', company.upload_logo)])
app.add_routes([web.get('/company/{id}/logo', company.get_logo)])

app.add_routes([web.get('/filings', filing.get_filings)])
app.add_routes([web.get('/filing/{id}', filing.get_filing)])
app.add_routes([web.put('/filing/{id}', filing.put_filing)])
app.add_routes([web.delete('/filing/{id}', filing.delete_filing)])
app.add_routes([web.post('/filing/{id}/signature', filing.upload_signature)])
app.add_routes([web.get('/filing/{id}/signature', filing.get_signature)])
app.add_routes([web.get('/filing/{id}/report', filing.get_report)])
app.add_routes([web.get('/filing/{id}/data', filing.get_data)])
app.add_routes([web.get('/filing/{id}/status', filing.get_status)])
app.add_routes([web.post('/filing/{id}/move-draft', filing.move_draft)])

app.add_routes([web.post('/books/{id}/upload', books.upload)])
app.add_routes([web.get('/books/{id}/info', books.get_info)])
app.add_routes([web.get('/books/{id}/summary', books.get_summary)])
app.add_routes([web.delete('/books/{id}', books.delete)])
app.add_routes([web.get('/books', books.get_all)])

app.add_routes([web.get('/vat/liabilities/{id}', vat.get_liabilities)])
app.add_routes([web.get('/vat/obligations/{id}', vat.get_obligations)])
app.add_routes([web.get('/vat/open-obligations/{id}',
                        vat.get_open_obligations)])
app.add_routes([web.get('/vat/payments/{id}', vat.get_payments)])

app.add_routes([web.post('/vat/compute/{id}', vat.compute)])
app.add_routes([web.post('/vat/submit/{id}', vat.submit)])

app.add_routes([web.post('/accounts/submit/{id}', accounts.submit)])

app.add_routes([web.post('/corptax/submit/{id}', corptax.submit)])

app.add_routes([web.get('/vat/receive-token', vat.receive_token)])
app.add_routes([web.get('/vat/authorize/{id}', vat.redirect_auth)])
app.add_routes([web.post('/vat/deauthorize/{id}', vat.deauthorize)])

app.add_routes([web.post('/corptax/authorize/{id}', corptax.authorize)])
app.add_routes([web.post('/corptax/deauthorize/{id}', corptax.deauthorize)])

app.add_routes([web.post('/accounts/authorize/{id}', accounts.authorize)])
app.add_routes([web.post('/accounts/deauthorize/{id}', accounts.deauthorize)])

app.add_routes([web.get('/status', status.get_all)])
app.add_routes([web.get('/status/{id}', status.get)])

app.add_routes([web.get('/company-reg/{id}', creg.get)])

web.run_app(app, port=config["port"])

