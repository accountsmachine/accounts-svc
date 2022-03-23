
import json
from aiohttp import web
import aiohttp
import glob
import logging

logger = logging.getLogger("company")
logger.setLevel(logging.DEBUG)

class Company():

    def __init__(self):
        pass

    async def get_all(self, request):

        request["auth"].verify_scope("company")
        user = request["auth"].user

        try:
            cs = await request["state"].company().list()
            return web.json_response(cs)
        except Exception as e:
            logger.debug("get_all: %s", e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def get(self, request):

        request["auth"].verify_scope("company")
        user = request["auth"].user

        try:

            id = request.match_info['id']

            if ".." in id:
                raise RuntimeError("Invalid id")

            data = await request["state"].company().get(id)

            return web.json_response(data)

        except Exception as e:
            logger.debug("get: %s", e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def put(self, request):

        request["auth"].verify_scope("company")
        user = request["auth"].user

        try:

            id = request.match_info['id']

            if ".." in id:
                raise RuntimeError("Invalid id")

            config = await request.json()
            await request["state"].company().put(id, config)
            return web.Response()

        except Exception as e:
            logger.debug("put: %s", e)

            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def delete(self, request):

        request["auth"].verify_scope("company")
        user = request["auth"].user

        try:

            id = request.match_info['id']

            if ".." in id:
                raise RuntimeError("Invalid id")

            for fid in await request["state"].filing_config().list():

                filing = await request["state"].filing_config().get(fid)

                if "company" in filing and filing["company"] == id:

                    try:
                        await request["state"].filing_report().delete(fid)
                    except:
                        pass

                    try:
                        await request["state"].filing_data().delete(fid)
                    except:
                        pass

                    try:
                        await request["state"].filing_status().delete(fid)
                    except:
                        pass

                    try:
                        await request["state"].signature_info().delete(fid)
                    except:
                        pass

                    try:
                        await request["state"].signature().delete(fid)
                    except:
                        pass

                    await request["state"].filing_config().delete(fid)

            try:
                await request["state"].books().delete(id)
            except: pass

            try:
                await request["state"].booksinfo().delete(id)
            except: pass

            try:
                await request["state"].logo().delete(id)
            except: pass

            try:
                await request["state"].logoinfo().delete(id)
            except: pass

            try:
                await request["state"].vat_auth().delete(id)
            except: pass

            try:
                await request["state"].corptax_auth().delete(id)
            except: pass

            try:
                await request["state"].accounts_auth().delete(id)
            except: pass

            try:
                await request["state"].company().delete(id)
            except: pass


            return web.Response()

        except Exception as e:
            logger.debug("delete: %s", e)

            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def upload_logo(self, request):

        request["auth"].verify_scope("company")
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

                    await request["state"].logo().put(id, payload)

                    await request["state"].logoinfo().put(id, {
                        "content-type": ctype,
                    })

            return web.Response()

        except Exception as e:
            logger.debug("upload_logo: %s", e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def get_logo(self, request):

        request["auth"].verify_scope("company")
        user = request["auth"].user

        try:

            id = request.match_info['id']

            if ".." in id:
                raise RuntimeError("Invalid id")

            info = await request["state"].logoinfo().get(id)
            ctype = info["content-type"]

            data = await request["state"].logo().get(id)

            return web.Response(body=data, content_type=ctype)

        except Exception as e:
            logger.debug("get_logo: %s", e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )
