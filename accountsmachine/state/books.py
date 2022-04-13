
from aiohttp import web
import datetime
import logging
import os
import uuid

from ixbrl_reporter.accounts import get_class

logger = logging.getLogger("books")
logger.setLevel(logging.DEBUG)

class Books:
    def __init__(self, state, id):
        self.state = state
        self.id = id
    async def get_info(self):
        return await self.state.booksinfo().get(self.id)
    async def put_info(self, data):
        await self.state.booksinfo().put(self.id, data)
    async def put(self, data):
        await self.state.books().put(self.id, data)
    async def delete(self):
        await self.state.booksinfo().delete(self.id)
        await self.state.books().delete(self.id)

    def default_mapping(self):
        data = {
            "vat-output-sales": [ "VAT:Output:Sales" ],
            "vat-output-acquisitions": [ "VAT:Output:EU" ],
            "vat-input": [ "VAT:Input" ],
            "total-vatex-sales": [
                "Assets:Capital Equipment:EU Reverse VAT Purchase",
                "Income"
            ],
            "total-vatex-purchases": [
                "Assets:Capital Equipment",
                "Expenses:VAT Purchases",
                "Expenses:VAT Purchases:EU Reverse VAT"
            ],
            "total-vatex-goods-supplied": [
                "Income:Sales:EU:Goods"
            ],
            "total-vatex-acquisitions": [
                "Expenses:VAT Purchases:EU Reverse VAT"
            ],
        }

    async def get_mapping(self):
        try:
            return await self.state.books_mapping().get(self.id)
        except:
            return self.default_mapping()

    async def put_mapping(self, data):
        await self.state.books_mapping().put(self.id, data)

    @staticmethod
    async def get_all_info(state):
        return await state.booksinfo().list()

    async def open_accounts(self, tmp_file):

        class AccountsCtxt:
            def __init__(self, books, file, kind):
                self.file = file
                open(file, "wb").write(books)
                cls = get_class(kind)
                self.accounts = cls(file)
            def __enter__(self):
                return self.accounts
            def __exit__(self, type, value, traceback):
                os.remove(self.file)

        books = await self.state.books().get(self.id)

        return AccountsCtxt(books, tmp_file, "piecash")

    def summarise(self, accts):

        start = datetime.date(1970, 1, 1)
        end = datetime.datetime.utcnow().date()

        alist = accts.get_accounts()

        res = []

        for a in alist:
            acc = accts.get_account(None, a)
            spl = accts.get_splits(acc, start, end)
            tot = 0
            for s in spl:
                tot += s["amount"]

            res.append({
                "account": a,
                "balance": round(tot, 2)
            })

        return res

