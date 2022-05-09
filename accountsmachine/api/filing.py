
import json
from aiohttp import web
import glob
import logging

from .. state import Filing
from . import standard

logger = logging.getLogger("api.filing")
logger.setLevel(logging.DEBUG)

class FilingApi():

    def __init__(self):
        pass

    async def get_all(self, request):
        h = standard.get_all(self, "filing-config", Filing)
        return await h(self, request)

    async def get(self, request):
        h = standard.get(self, "filing-config", Filing)
        return await h(self, request)

    async def put(self, request):
        h = standard.put(self, "filing-config", Filing)
        return await h(self, request)

    async def delete(self, request):
        h = standard.delete(self, "filing-config", Filing)
        return await h(self, request)

    async def upload_signature(self, request):

        request["auth"].verify_scope("filing-config")
        user = request["auth"].user
        id = request.match_info['id']

        f = Filing(request["state"], id)

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

                    await f.put_signature(payload, ctype)

            return web.Response()

        except Exception as e:
            logger.debug("Exception: %s", e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def get_signature(self, request):

        request["auth"].verify_scope("filing-config")
        user = request["auth"].user
        id = request.match_info['id']

        f = Filing(request["state"], id)

        img, ctype = await f.get_signature()

        return web.Response(body=img, content_type=ctype)

    async def get_report(self, request):

        request["auth"].verify_scope("filing-config")
        user = request["auth"].user
        id = request.match_info['id']

        f = Filing(request["state"], id)

        data = await f.get_report()
        text = data.decode("utf-8")

        return web.Response(body=text, content_type="text/html")

    async def get_data(self, request):

        request["auth"].verify_scope("filing-config")
        user = request["auth"].user
        id = request.match_info['id']

        f = Filing(request["state"], id)

        data = await f.get_data()

        return web.json_response(data)

    async def get_status(self, request):

        request["auth"].verify_scope("filing-config")
        user = request["auth"].user
        id = request.match_info['id']

        f = Filing(request["state"], id)

        data = await f.get_status()

        return web.json_response(data)

    async def move_draft(self, request):

        request["auth"].verify_scope("filing-config")
        user = request["auth"].user

        try:

            id = request.match_info['id']

            if ".." in id:
                raise RuntimeError("Invalid id")

            cfg = await request["state"].filing(id).get()

            if "state" in cfg:
                if cfg["state"] in ["errored", "pending"]:
                    cfg["state"] = "draft"
                else:
                    raise RuntimeError("Not OK")
            else:
                raise RuntimeError("Not OK")

            cfg = await request["state"].filing(id).put(cfg)

            return web.Response()

        except Exception as e:
            logger.debug("Exception: %s", e)

            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )
