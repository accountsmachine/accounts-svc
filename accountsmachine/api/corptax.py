
import asyncio
from aiohttp import web
from aiohttp import ClientSession
from urllib.parse import urlencode, quote_plus
import datetime
import json
import logging

from .. ixbrl_process import IxbrlProcess

logger = logging.getLogger("api.corptax")
logger.setLevel(logging.DEBUG)

class CorptaxApi():
    def __init__(self):
        pass

    async def background_submit(self, user, renderer, id, kind):

        try:

            try:
                await user.filing(id).delete_report()
            except: pass

            try:
                await user.filing(id).data().delete()
            except: pass

            try:
                await user.filing(id).status().delete()
            except: pass

            try:
                html = await renderer.render(
                    user, renderer, id, kind
                )

                i = IxbrlProcess()
                vals = i.process_with_schema(html)

            except Exception as e:

                await user.filing(id).status().put({
                    "report": str(e)
                })

                await user.filing(id).put_report("".encode("utf-8"))

                cfg = await user.filing(id).get()
                cfg["user"] = "errored"
                cfg = await user.filing(id).put(cfg)

                return

            await user.filing(id).put_report(html.encode("utf-8"))
            await user.filing(id).data().put(vals)
            await user.filing(id).status().put({
                "report": """Submitting...
Validating...
Connecting made...
Filing complete."""
            })

            cfg = await user.filing(id).get()
            cfg["user"] = "pending"
            cfg = await user.filing(id).put(cfg)

            await asyncio.sleep(5)

            cfg = await user.filing(id).get()
            cfg["state"] = "published"
            cfg = await user.filing(id).put(cfg)

        except Exception as e:

            logger.debug("submit: Exception: %s", e)

            try:
                await user.filing(id).status().put({
                    "report": str(e)
                })
            except: pass

    async def submit(self, request):

        request["auth"].verify_scope("accounts")

        try:

            id = request.match_info['id']
            kind = "corptax"

            asyncio.create_task(
                self.background_submit(request["state"], 
                                       request["renderer"], id, kind)
            )

            return web.json_response()

        except Exception as e:

            logger.debug("submit: Exception: %s", e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def authorize(self, request):

        request["auth"].verify_scope("corptax")
        user = request["state"]

        try:

            id = request.match_info['id']

            config = await request.json()
            await user.company(id).corptax_auth().put(config)
            return web.Response()

        except Exception as e:
            logger.debug("Exception: %s", e)

            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def deauthorize(self, request):

        request["auth"].verify_scope("corptax")
        user = request["state"]

        try:

            id = request.match_info['id']

            await user.company(id).corptax_auth().delete()
            return web.Response()

        except Exception as e:
            logger.debug("Exception: %s", e)

            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

