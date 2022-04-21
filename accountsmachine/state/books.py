
import datetime
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

        books = await self.company.books().get_accounts()

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

