
from datetime import datetime, date, timezone
import logging
import os

from ixbrl_reporter.accounts import get_class

logger = logging.getLogger("state.books")
logger.setLevel(logging.DEBUG)

class Books:

    def __init__(self, user, cid):
        self.user = user
        self.cid = cid
        self.company = user.company(cid)

    async def get_info(self):
        return await self.company.books().get()

    async def put_info(self, data):
        await self.company.books().put(data)

    async def put(self, data):
        await self.company.books().put_accounts(data)

    async def delete(self):
        await self.company.books().delete()

    def default_mapping(self):
        return {
            "vat-output-sales": [
                { "account": "VAT:Output:Sales", "reversed": False }
            ],
            "vat-output-acquisitions": [
                { "account": "VAT:Output:EU", "reversed": False }
            ],
            "vat-input": [
                { "account": "VAT:Input", "reversed": False }
            ],
            "total-vatex-sales": [
                {
                    "account": "Assets:Capital Equipment:EU Reverse VAT Purchase",
                    "reversed": False
                },
                { "account": "Income", "reversed": False }
            ],
            "total-vatex-purchases": [
                {
                    "account": "Assets:Capital Equipment",
                    "reversed": False
                },
                {
                    "account": "Expenses:VAT Purchases",
                    "reversed": False
                },
                {
                    "account": "Expenses:VAT Purchases:EU Reverse VAT",
                    "reversed": True
                }
            ],
            "total-vatex-goods-supplied": [
                { "account": "Income:Sales:EU:Goods", "reversed": False }
            ],
            "total-vatex-acquisitions": [
                {
                    "account": "Expenses:VAT Purchases:EU Reverse VAT",
                    "reversed": False
                }
            ],
        }

    async def get_mapping(self):
        try:
            return await self.company.books_mapping().get()
        except:
            return self.default_mapping()

    async def put_mapping(self, data):
        await self.company.books_mapping().put(data)

    @staticmethod
    async def get_all_info(user):

        cmps = await user.companies().list()

        ret = {}

        for cmp in cmps:
            try:
                b = await user.company(cmp).books().get()
                ret[cmp] = b
            except:
                pass

        return ret

    async def validate(self, blob, kind):

        if kind == "gnucash-sqlite":
            return

        if kind == "csv":
            return

        raise RuntimeError("Format '%s' not recognised" % kind)

    async def create_temp_file(self, tmp_file):

        class FileContext:
            def __init__(self, books, file):
                self.file = file
                open(file, "wb").write(books)
            def __enter__(self):
                return self.file
            def __exit__(self, type, value, traceback):
                os.remove(self.file)

        books = await self.company.books().get_accounts()

        return FileContext(books, tmp_file)

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

        info = await self.get_info()

        books = await self.company.books().get_accounts()

        kind = info["kind"]

        if kind == "gnucash-sqlite":
            return AccountsCtxt(books, tmp_file, "piecash")

        if kind == "csv":
            return AccountsCtxt(books, tmp_file, "csv")

        raise RuntimeError("Cannot process accounting books kind '%s'" % kind)

    def summarise(self, accts):

        start = date(1970, 1, 1)
        end = datetime.now(timezone.utc).date()

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

