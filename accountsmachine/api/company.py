
import json
from aiohttp import web
import aiohttp
import glob
import logging

from .. state import Company
from . import standard

logger = logging.getLogger("api.company")
logger.setLevel(logging.DEBUG)

class CompanyApi:

    def __init__(self):
        pass

    async def get_all(self, request):
        h = standard.get_all(self, "company", Company)
        return await h(self, request)

    async def get(self, request):
        h = standard.get(self, "company", Company)
        return await h(self, request)

    async def put(self, request):
        h = standard.put(self, "company", Company)
        return await h(self, request)

    async def delete(self, request):
        h = standard.delete(self, "company", Company)
        return await h(self, request)

    async def upload_logo(self, request):

        request["auth"].verify_scope("company")
        user = request["auth"].user
        id = request.match_info['id']

        c = Company(request["state"], id)

        try:
            reader = await request.multipart()

            while True:
                field = await reader.next()
                if not field:
                    break

                if field.name == "image":
                    try:
                        ctype = field.headers[aiohttp.hdrs.CONTENT_TYPE]
                    except:
                        ctype = "image/png"

                    payload = bytes()

                    size = 0
                    while True:
                        chunk = await field.read_chunk()
                        if not chunk:
                            break
                        size += len(chunk)
                        payload += chunk

                    await c.put_logo(payload, ctype)

            return web.Response()

        except Exception as e:
            logger.debug("upload_logo: %s", e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def get_logo(self, request):

        request["auth"].verify_scope("company")
        user = request["auth"].user
        id = request.match_info['id']

        c = Company(request["state"], id)

        try:
            logo = await c.get_logo()
            type = await c.get_logo_type()
        except KeyError:
            return web.HTTPNotFound()

        return web.Response(body=logo, content_type=type)

