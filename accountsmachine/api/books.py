
from aiohttp import web
import datetime
import logging
import os
import uuid

from .. state import Books

from ixbrl_reporter.accounts import get_class

logger = logging.getLogger("api.books")
logger.setLevel(logging.DEBUG)

class BooksApi:

    async def get_info(self, request):

        request["auth"].verify_scope("books")
        user = request["state"]
        cid = request.match_info['id']

        books = Books(user, cid)

        try:
            info = await books.get_info()
        except:
            return web.HTTPNotFound()

        return web.json_response(info)

    async def get_mapping(self, request):

        request["auth"].verify_scope("books")
        user = request["state"]
        cid = request.match_info['id']

        books = Books(user, cid)

        info = await books.get_mapping()

        return web.json_response(info)

    async def put_mapping(self, request):

        request["auth"].verify_scope("books")
        user = request["state"]
        cid = request.match_info['id']
        data = await request.json()

        books = Books(user, cid)

        try:
            await books.put_mapping(data)
            return web.Response()
        except Exception as e:
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def delete(self, request):

        request["auth"].verify_scope("books")
        user = request["state"]
        cid = request.match_info['id']

        books = Books(user, cid)

        await books.delete()

        return web.json_response()

    async def upload(self, request):

        request["auth"].verify_scope("books")
        user = request["state"]
        cid = request.match_info['id']

        books = Books(user, cid)

        try:

            blob = None
            kind = None
            size = None

            reader = await request.multipart()

            while True:

                field = await reader.next()
                if not field: break

                if field.name == "books":

                    blob = bytes()

                    size = 0
                    while True:
                        chunk = await field.read_chunk()
                        if not chunk:
                            break
                        size += len(chunk)
                        blob += chunk

                if field.name == "kind":
                    kind = ""
                    while True:
                        chunk = await field.read_chunk()
                        if not chunk:
                            break
                        kind += chunk.decode("utf-8")

            if blob == None or kind == None:
                return web.HTTPBadRequest(
                    body="Need 'books' and 'kind' fields"
                )

            await books.put(blob)
            await books.put_info({
                "time": datetime.datetime.utcnow().isoformat(),
                "length": size,
                "kind": kind,
            })

            try:
                await books.validate(blob, kind)
            except Exception as e:
                return web.HTTPBadRequest(body=str(e))

            return web.Response()

        except Exception as e:
            logger.debug(e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def get_all(self, request):

        request["auth"].verify_scope("books")
        user = request["state"]

        try:
            data = await Books.get_all_info(user)
            return web.json_response(data)
        except Exception as e:
            logger.debug(e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def get_summary(self, request):

        request["auth"].verify_scope("books")
        user = request["state"]
        cid = request.match_info['id']

        books = Books(user, cid)

        tmp_file = "tmp." + str(uuid.uuid4()) + ".tmp"

        try:
            with await books.open_accounts(tmp_file) as accts:
                s = books.summarise(accts)
        except Exception as e:
            logger.error(e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

        return web.json_response(s)

