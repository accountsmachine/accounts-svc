
import asyncio
from aiohttp import web
from aiohttp import ClientSession
from urllib.parse import urlencode, quote_plus
import datetime
import json
import logging

from . ixbrl_process import IxbrlProcess

logger = logging.getLogger("corptax")
logger.setLevel(logging.DEBUG)

class Corptax():
    def __init__(self):
        pass

    async def background_submit(self, state, books, renderer, id, kind):

        try:

            try:
                await state.filing_report().delete(id)
            except: pass

            try:
                await state.filing_data().delete(id)
            except: pass

            try:
                await state.filing_status().delete(id)
            except: pass

            try:
                html = await renderer.render(
                    state, books, renderer, id, kind
                )

                i = IxbrlProcess()
                vals = i.process_with_schema(html)

            except Exception as e:

                await state.filing_status().put(id, {
                    "report": str(e)
                })

                await state.filing_report().put(id, "")

                cfg = await state.filing_config().get(id)
                cfg["state"] = "errored"
                cfg = await state.filing_config().put(id, cfg)

                return

            await state.filing_report().put(id, html)
            await state.filing_data().put(id, vals)
            await state.filing_status().put(id, {
                "report": """Submitting...
Validating...
Connecting made...
Filing complete."""
            })

            cfg = await state.filing_config().get(id)
            cfg["state"] = "pending"
            cfg = await state.filing_config().put(id, cfg)

            await asyncio.sleep(5)

            cfg = await state.filing_config().get(id)
            cfg["state"] = "published"
            cfg = await state.filing_config().put(id, cfg)

        except Exception as e:

            logger.debug("submit: Exception: %s", e)

            try:
                await state.filing_status().put(id, {
                    "report": str(e)
                })
            except: pass

    async def submit(self, request):

        request["auth"].verify_scope("accounts")
        user = request["auth"].user

        try:

            id = request.match_info['id']
            kind = "corptax"

            asyncio.create_task(
                self.background_submit(request["state"], request["books"],
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
        user = request["auth"].user

        try:

            id = request.match_info['id']

            if ".." in id:
                raise RuntimeError("Invalid id")

            config = await request.json()
            await request["state"].corptax_auth().put(id, config)
            return web.Response()

        except Exception as e:
            logger.debug("Exception: %s", e)

            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def deauthorize(self, request):

        request["auth"].verify_scope("corptax")
        user = request["auth"].user

        try:

            id = request.match_info['id']

            if ".." in id:
                raise RuntimeError("Invalid id")

            await request["state"].corptax_auth().delete(id)
            return web.Response()

        except Exception as e:
            logger.debug("Exception: %s", e)

            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

