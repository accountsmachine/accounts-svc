
from aiohttp import web
import datetime
import logging
import os
import uuid

from .. state import Books

from ixbrl_reporter.accounts import get_class

logger = logging.getLogger("books")
logger.setLevel(logging.DEBUG)

class BooksApi:

    async def get_info(self, request):

        request["auth"].verify_scope("books")
        user = request["auth"].user
        id = request.match_info['id']

        books = Books(request["state"], id)

        try:
            info = await books.get_info()
        except:
            return web.HTTPNotFound()

        return web.json_response(info)

    async def get_mapping(self, request):

        request["auth"].verify_scope("books")
        user = request["auth"].user
        id = request.match_info['id']

        books = Books(request["state"], id)

        try:
            info = await books.get_mapping()
        except:
            return web.HTTPNotFound()

        return web.json_response(info)

    async def put_mapping(self, request):

        request["auth"].verify_scope("books")
        user = request["auth"].user
        id = request.match_info['id']
        data = await request.json()

        books = Books(request["state"], id)

        try:
            await books.put_mapping(data)
            return web.Response()
        except Exception as e:
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def delete(self, request):

        request["auth"].verify_scope("books")
        user = request["auth"].user
        id = request.match_info['id']

        books = Books(request["state"], id)

        await books.delete()

        return web.json_response()

    async def upload(self, request):

        request["auth"].verify_scope("books")
        user = request["auth"].user
        id = request.match_info['id']

        books = Books(request["state"], id)

        try:

            reader = await request.multipart()

            while True:

                field = await reader.next()
                if not field: break

                if field.name == "books":

                    payload = bytes()

                    size = 0
                    while True:
                        chunk = await field.read_chunk()
                        if not chunk:
                            break
                        size += len(chunk)
                        payload += chunk

                    await books.put(payload)
                    await books.put_info({
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
            data = await Books.get_all_info(request["state"])
            return web.json_response(data)
        except Exception as e:
            logger.debug(e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def get_summary(self, request):

        request["auth"].verify_scope("books")
        user = request["auth"].user
        id = request.match_info['id']

        books = Books(request["state"], id)

        tmp_file = "tmp." + str(uuid.uuid4()) + ".tmp"

        with await books.open_accounts(tmp_file) as accts:
            s = books.summarise(accts)

        return web.json_response(s)

