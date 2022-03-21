
import json
from aiohttp import web
import glob
import logging

logger = logging.getLogger("filing")
logger.setLevel(logging.DEBUG)

class Filing():

    def __init__(self):
        pass

    async def get_filings(self, request):

        request["auth"].verify_scope("filing-config")
        user = request["auth"].user

        try:

            resp = await request["state"].filing_config().list()
            return web.json_response(
                resp,
                headers={'X-Object-Type': 'FilingItem[]'}
            )

        except Exception as e:
            logger.debug("Exception: %s", e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def get_filing(self, request):

        request["auth"].verify_scope("filing-config")
        user = request["auth"].user

        try:

            id = request.match_info['id']

            if ".." in id:
                raise RuntimeError("Invalid id")

            data = await request["state"].filing_config().get(id)

            return web.json_response(
                data,
                headers={'X-Object-Type': 'FilingItem'}
            )

        except Exception as e:
            logger.debug("Exception: %s", e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def put_filing(self, request):

        request["auth"].verify_scope("filing-config")
        user = request["auth"].user

        try:

            id = request.match_info['id']

            if ".." in id:
                raise RuntimeError("Invalid id")

            config = await request.json()
            await request["state"].filing_config().put(id, config)
            return web.Response()

        except Exception as e:
            logger.debug("Exception: %s", e)

            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def delete_filing(self, request):

        request["auth"].verify_scope("filing-config")
        user = request["auth"].user

        try:

            id = request.match_info['id']

            if ".." in id:
                raise RuntimeError("Invalid id")

            try:
                await request["state"].filing_report().delete(id)
            except:
                pass

            try:
                await request["state"].filing_data().delete(id)
            except:
                pass

            try:
                await request["state"].filing_status().delete(id)
            except:
                pass

            await request["state"].filing_config().delete(id)
            return web.Response()

        except Exception as e:
            logger.debug("Exception: %s", e)

            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def upload_signature(self, request):

        request["auth"].verify_scope("filing-config")
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

                    await request["state"].signature().put(id, payload)
                    await request["state"].signatureinfo().put(id, {
                        "content-type": ctype,
                    })

            return web.Response()

        except Exception as e:
            logger.debug("Exception: %s", e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def get_signature(self, request):

        request["auth"].verify_scope("filing-config")
        user = request["auth"].user

        try:

            id = request.match_info['id']

            if ".." in id:
                raise RuntimeError("Invalid id")

            info = await request["state"].signatureinfo().get(id)
            ctype = info["content-type"]

            data = await request["state"].signature().get(id)

            return web.Response(body=data, content_type=ctype)

        except Exception as e:
            logger.debug("Exception: %s", e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def get_report(self, request):

        request["auth"].verify_scope("filing-config")
        user = request["auth"].user

        try:

            id = request.match_info['id']

            data = await request["state"].filing_report().get(id)

            return web.json_response(data)

        except Exception as e:
            logger.debug("Exception: %s", e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def get_data(self, request):

        request["auth"].verify_scope("filing-config")
        user = request["auth"].user

        try:

            id = request.match_info['id']

            data = await request["state"].filing_data().get(id)

            return web.json_response(data)

        except Exception as e:
            logger.debug("Exception: %s", e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def get_status(self, request):

        request["auth"].verify_scope("filing-config")
        user = request["auth"].user

        try:

            id = request.match_info['id']

            status = await request["state"].filing_status().get(id)

            return web.json_response(status)

        except Exception as e:
            logger.debug("Exception: %s", e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def move_draft(self, request):

        request["auth"].verify_scope("filing-config")
        user = request["auth"].user

        try:

            id = request.match_info['id']

            if ".." in id:
                raise RuntimeError("Invalid id")

            cfg = await request["state"].filing_config().get(id)

            if "state" in cfg:
                if cfg["state"] in ["errored", "pending"]:
                    cfg["state"] = "draft"
                else:
                    raise RuntimeError("Not OK")
            else:
                raise RuntimeError("Not OK")

            cfg = await request["state"].filing_config().put(id, cfg)

            return web.Response()

        except Exception as e:
            logger.debug("Exception: %s", e)

            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )
