
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

    async def compute(self, user, renderer, id):

        try:
            html = await renderer.render(user, renderer, id, "vat")
        except Exception as e:
            html = ""
            logger.error(e)

        i = IxbrlProcess()
        vat = i.process(html)

        return vat

    async def get_hmrc_client(self, config, user, cid):
        auth = user.company(cid).vat_auth()
        cmp = await user.company(cid).get()
        vrn = cmp["vrn"]
        return Hmrc(config, auth, vrn)

    async def get_status(self, config, user, cid, start, end):
        cli = await self.get_hmrc_client(config, user, cid)
        l, p, o = await cli.get_status(start, end)

        return {
            "liabilities": [v.to_dict() for v in l],
            "payments": [v.to_dict() for v in p],
            "obligations": [v.to_dict() for v in o]
        }

    async def get_liabilities(self, config, user, cid, start, end):
        cli = await self.get_hmrc_client(config, user, cid)
        l = await cli.get_vat_liabilities(start, end)
        return [v.to_dict() for v in l]

    async def get_obligations(self, config, user, cid, start, end):
        cli = await self.get_hmrc_client(config, user, cid)
        l = await cli.get_obligations(start, end)
        return [v.to_dict() for v in l]

    async def get_open_obligations(self, config, user, cid):
        cli = await self.get_hmrc_client(config, user, cid)
        l = await cli.get_open_obligations()
        return [v.to_dict() for v in l]

    async def get_payments(self, config, user, cid, start, end):
        cli = await self.get_hmrc_client(config, user, cid)
        l = await cli.get_payments(start, end)
        return [v.to_dict() for v in l]

    async def submit(self, uid, email, config, user, renderer, id):

        cfg = await user.filing(id).get()
        cid = cfg["company"]

        cli = await self.get_hmrc_client(config, user, cid)

        vs = VatSubmission(cli, uid, email, user, renderer)
        await vs.submit(id)

    async def get_auth_ref(self, uid, user, cid):

        secret = secrets.token_hex(32)

        token = {
            "secret": secret,
            "company": cid,
            "time": int(time.time()),
        }
        
        await user.company(cid).vat_auth_placeholder().put(token)

        return uid + ":" + cid + ":" + secret

    async def receive_token(self, code, state):

        # Don't trust the inputs. uid may not be valid
        uid, cid, secret = state.split(":", 2)

        user = State(self.store).user(uid)

        token = await user.company(cid).vat_auth_placeholder().get()

        if secret != token["secret"]:
            raise RuntimeError("Token not valid")

        if cid != token["company"]:
            raise RuntimeError("Token not valid")

        return uid, cid

    async def store_auth(self, uid, company, auth):

        cmp = State(self.store).user(uid).company(company)
        await cmp.vat_auth().put(auth)
        await cmp.vat_auth_placeholder().delete()

