
import time
import logging
import secrets

logger = logging.getLogger("vat.vat")
logger.setLevel(logging.DEBUG)

from .. ixbrl_process import IxbrlProcess
from .. state import State

from . submit import VatSubmission
from . hmrc import Hmrc

class Vat:

    def __init__(self, config, store):

        self.client_id = config["vat-client-id"]
        self.client_secret = config["vat-client-secret"]
        self.redirect_uri = config["redirect-uri"]
        self.store = store

    async def compute(self, state, renderer, id):

        try:
            html = await renderer.render(state, renderer, id, "vat")
        except Exception as e:
            html = ""
            logger.error(e)

        i = IxbrlProcess()
        vat = i.process(html)

        return vat

    async def get_status(self, config, state, id, start, end):
        cli = Hmrc(config, state, id)
        l, p, o = await cli.get_status(start, end)

        return {
            "liabilities": [v.to_dict() for v in l],
            "payments": [v.to_dict() for v in p],
            "obligations": [v.to_dict() for v in o]
        }

    async def get_liabilities(self, config, state, id, start, end):
        cli = Hmrc(config, state, id)
        l = await cli.get_vat_liabilities(start, end)
        return [v.to_dict() for v in l]

    async def get_obligations(self, config, state, id, start, end):
        cli = Hmrc(config, state, id)
        l = await cli.get_obligations(start, end)
        return [v.to_dict() for v in l]

    async def get_open_obligations(self, config, state, id):
        cli = Hmrc(config, state, id)
        l = await cli.get_open_obligations()
        return [v.to_dict() for v in l]

    async def get_payments(self, config, state, id, start, end):
        cli = Hmrc(config, state, id)
        l = await cli.get_payments(start, end)
        return [v.to_dict() for v in l]

    async def submit(self, user, email, config, state, renderer, id):

        vs = VatSubmission(user, email, config, state, renderer)
        await vs.submit(id)

    async def get_auth_ref(self, uid, state, cmp):

        secret = secrets.token_hex(32)

        token = {
            "secret": secret,
            "company": cmp,
            "time": int(time.time()),
        }
        
        await state.vat_auth_ref().put("ref", token)

        return uid + ":" + secret

    async def receive_token(self, code, state):

        # Don't trust the inputs. uid may not be valid
        uid, secret = state.split(":", 1)

        state = State(self.store, uid)

        token = await state.vat_auth_ref().get("ref")

        if secret != token["secret"]:
            raise RuntimeError("Token not valid")

        company = token["company"]

        return uid, company

    async def store_auth(self, uid, company, auth):

        state = State(self.store, uid)
        await state.vat_auth().put(company, auth)
        await state.vat_auth_ref().delete("ref")

