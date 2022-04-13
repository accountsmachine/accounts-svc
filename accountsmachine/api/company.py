
import json
from aiohttp import web
import aiohttp
import glob
import logging

from .. state import Company

logger = logging.getLogger("api.company")
logger.setLevel(logging.DEBUG)

class CompanyApi:

    def __init__(self):
        pass

    async def get_all(self, request):

        request["auth"].verify_scope("company")
        user = request["auth"].user

        try:
            cs = await Company.get_all(request["state"])
            return web.json_response(cs)
        except Exception as e:
            logger.debug("get_all: %s", e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def get(self, request):

        request["auth"].verify_scope("company")
        user = request["auth"].user
        id = request.match_info['id']

        c = Company(request["state"], id)

        try:
            info = await c.get()
        except KeyError:
            return web.HTTPNotFound()

        return web.json_response(info)

    async def put(self, request):

        request["auth"].verify_scope("company")
        user = request["auth"].user
        id = request.match_info['id']
        info = await request.json()

        c = Company(request["state"], id)

        try:
            await c.put(info)
            return web.json_response()
        except Exception as e:
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def delete(self, request):

        request["auth"].verify_scope("company")
        user = request["auth"].user
        id = request.match_info['id']

        c = Company(request["state"], id)

        try:
            await c.delete()
            return web.json_response()
        except Exception as e:
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

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

