
from aiohttp import web
import datetime
import logging
import os
import uuid

from ixbrl_reporter.accounts import get_class

logger = logging.getLogger("books")
logger.setLevel(logging.DEBUG)

class Books:

    def __init__(self):
        pass

    async def get_info(self, request):

        request["auth"].verify_scope("books")
        user = request["auth"].user

        id = request.match_info['id']

        if ".." in id:
            raise RuntimeError("Invalid id")

        try:
            return web.json_response(
                await request["state"].booksinfo().get(id)
            )
        except Exception as e:
            return web.HTTPNotFound()

    async def delete(self, request):

        request["auth"].verify_scope("company")
        user = request["auth"].user

        id = request.match_info['id']

        if ".." in id:
            raise RuntimeError("Invalid id")

        try:
            await request["state"].booksinfo().delete(id)
        except: pass

        await request["state"].books().delete(id)

        return web.Response()

    async def upload(self, request):

        request["auth"].verify_scope("books")
        user = request["auth"].user

        try:

            id = request.match_info['id']

            if ".." in id:
                raise RuntimeError("Invalid id")

            reader = await request.multipart()

            while True:

                field = await reader.next()

                if not field:
                    break

                if field.name == "books":

                    books = bytes()

                    size = 0
                    while True:
                        chunk = await field.read_chunk()
                        if not chunk:
                            break
                        size += len(chunk)
                        books += chunk

                    await request["state"].books().put(id, books)

                    await request["state"].booksinfo().put(id, {
                        "time": datetime.datetime.utcnow().isoformat(),
                        "length": size
                    })

            return web.Response()

        except Exception as e:
            logger.debug(e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def get_all(self, request):
        request["auth"].verify_scope("books")
        user = request["auth"].user

        try:

            resp = await request["state"].booksinfo().list()
            return web.json_response(resp)

        except Exception as e:
            logger.debug(e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def books(self, state, company_number, accts_file):

        try:
            books = await state.books().get(company_number)
            open(accts_file, "wb").write(books)
        except Exception as e:
            logger.debug("Exception: %s", e)
            raise RuntimeError("Could not load accounts file.")

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

    async def get_summary(self, request):

        request["auth"].verify_scope("books")
        user = request["auth"].user

        accts_file = "tmp." + str(uuid.uuid4()) + ".dat"

        id = request.match_info['id']

        if ".." in id:
            raise RuntimeError("Invalid id")

        try:

            await self.books(request["state"], id, accts_file)

            cls = get_class("piecash")
            accounts = cls(accts_file)

            res = self.summarise(accounts)

            os.remove(accts_file)

            return web.json_response(res)

        except Exception as e:
            print(e)

            try:
                os.remove(accts_file)
            except:
                pass

            return web.HTTPNotFound()

    async def get_mapping(self, request):

        request["auth"].verify_scope("books")
        user = request["auth"].user

        try:

            id = request.match_info['id']

            if ".." in id:
                raise RuntimeError("Invalid id")

            try:
                data = await request["state"].books_mapping().get(id)
            except KeyError:
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
                await request["state"].books_mapping().put(id, data)

            return web.json_response(data)

        except Exception as e:
            logger.debug("get: %s", e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def put_mapping(self, request):

        request["auth"].verify_scope("books")
        user = request["auth"].user

        try:

            id = request.match_info['id']

            if ".." in id:
                raise RuntimeError("Invalid id")

            config = await request.json()
            await request["state"].books_mapping().put(id, config)
            return web.Response()

        except Exception as e:
            logger.debug("put: %s", e)

            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )
