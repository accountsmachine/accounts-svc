
import time
import logging
import secrets
import uuid
from datetime import date, datetime, timezone

logger = logging.getLogger("vat.vat")
logger.setLevel(logging.DEBUG)

from .. ixbrl_process import IxbrlProcess
from .. state import State
from .. state.books import Books

from . submit import VatSubmission
from . hmrc import Hmrc

class Vat:

    def __init__(self, config, store):

        self.client_id = config["vat-client-id"]
        self.client_secret = config["vat-client-secret"]
        self.redirect_uri = config["redirect-uri"]
        self.store = store

    async def calculate(self, user, renderer, id):

        try:

            cfg = await user.filing(id).get()

            try:
                cid = cfg["company"]
            except Exception as e:
                raise RuntimeError("No company number in configuration")

            cmp = await user.company(cid).get()

            books = Books(user, cid)

            info = await books.get_info()
            mappings = await books.get_mapping()

            tmp_file = "tmp." + str(uuid.uuid4()) + ".dat"

            start = date.fromisoformat(cfg["start"])
            end = date.fromisoformat(cfg["end"])

            calcs = {}

            # There's too much negation going on here.  Need to negate
            # boxes 1, 2, 3, 7 and 9 to match what happens in
            # vat-computations.jsonnet
            vat_negate = set([
                "vat-output-sales",
                "vat-output-acquisitions",
                "vat-output-acquisitions",
                "total-vatex-purchases",
                "total-vatex-acquisitions"
            ])

            with await books.open_accounts(tmp_file) as accts:

                for line in mappings:

                    calcs[line] = {}

                    for acct in mappings[line]:

                        tot = 0
                        ah = accts.get_account(None, acct["account"])

                        if accts.is_debit(ah):
                            factor = -1
                        else:
                            factor = 1

                        if line in vat_negate:
                            factor = -factor

                        spl = accts.get_splits(ah, start, end)

                        txs = []

                        for s in spl:

                            tot += s["amount"]

                            txs.append({
                                "amount": s["amount"] * factor,
                                "description": s["description"],
                                "date": s["date"].isoformat(),
                            })

                        calcs[line][acct["account"]] = {
                            "transactions": txs,
                            "reversed": acct["reversed"],
                        }

            return calcs

        except Exception as e:
            logger.error(e)
            raise e

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

