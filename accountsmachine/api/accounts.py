
import asyncio
from aiohttp import web
from aiohttp import ClientSession
from urllib.parse import urlencode, quote_plus
import datetime
import json
import logging

from .. ixbrl_process import IxbrlProcess

logger = logging.getLogger("api.accounts")
logger.setLevel(logging.DEBUG)

class AccountsApi:
    def __init__(self):
        pass

    async def background_submit(self, state, renderer, id, kind):

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
                    state, renderer, id, kind
                )

                i = IxbrlProcess()
                vals = i.process_with_schema(html)

            except Exception as e:

                await state.filing_status().put(id, {
                    "report": str(e)
                })

                await state.filing_report().put(id, "".encode("utf-8"))

                cfg = await state.filing_config().get(id)
                cfg["state"] = "errored"
                cfg = await state.filing_config().put(id, cfg)

                return

            await state.filing_report().put(id, html.encode("utf-8"))
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
            kind = "accounts"

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

        request["auth"].verify_scope("accounts")
        user = request["state"]

        try:

            id = request.match_info['id']

            config = await request.json()
            await user.company(id).accounts_auth().put(config)
            return web.Response()

        except Exception as e:
            logger.debug("Exception: %s", e)

            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def deauthorize(self, request):

        request["auth"].verify_scope("accounts")
        user = request["state"]

        try:

            id = request.match_info['id']

            await user.company(id).accounts_auth().delete()
            return web.Response()

        except Exception as e:
            logger.debug("Exception: %s", e)

            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

