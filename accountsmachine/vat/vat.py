
from urllib.parse import urlencode, quote_plus
import datetime
import asyncio
import logging
from io import StringIO
import json
import uuid

import gnucash_uk_vat.hmrc as hmrc
import gnucash_uk_vat.model as model
import gnucash_uk_vat.auth as auth

logger = logging.getLogger("vat.vat")
logger.setLevel(logging.DEBUG)

from .. ixbrl_process import IxbrlProcess

# Like VAT, but talks to configuration endpoints
class VatEndpoint(hmrc.Vat):
    def __init__(self, config, auth):
        super().__init__(config, auth)
        self.oauth_base = config["vat-auth-url"]
        self.api_base = config["vat-api-url"]

    # Constructs HTTP headers which meet the Fraud API.  Most of this
    # comes from config
    def build_fraud_headers(self):

        dnt = self.config.get("identity.do-not-track")
        ua = self.config.get("identity.device.user-agent")
        dev_id = self.config.get("identity.device.id")
        my_ip = self.config.get("server.ip")

        mfa = [
#            ("type", "AUTH_CODE"),
#            ("timestamp", "2021-11-21T13:23Z"),
#            ("unique-reference", "fc4b5fd6816f75a7c"),
#            ("type", "TOTP"),
#            ("timestamp", "2021-11-21T13:20Z"),
#            ("unique-reference", "0283da60063abfb3a")
        ]

        mfa = "&".join([
            urlencode({v[0]: v[1]}) for v in mfa
        ])

        client_ip = self.config.get("identity.transport.host")
        client_port =  self.config.get("identity.transport.port")

        window = [
            ("width", self.config.get("window.width")),
            ("height", self.config.get("window.height"))
        ]

        window = "&".join([
            urlencode({v[0]: v[1]}) for v in window
        ])

        screens = [
            ("width", self.config.get("screen.width")),
            ("height", self.config.get("screen.height")),
            ("scaling-factor", self.config.get("screen.scaling-factor")),
            ("colour-depth", self.config.get("screen.colour-depth"))
        ]

        screens = "&".join([
            urlencode({v[0]: v[1]}) for v in screens
        ])

        user_ids = [
            ("accountsmachine.io", self.config.get("identity.user")),
            ("email", self.config.get("identity.email"))
        ]

        user_ids = "&".join([
            urlencode({v[0]: v[1]}) for v in user_ids
        ])

        hops = []

        xff = self.config.get("transport.forwarded")

        if len(xff) > 0:

            src = None

            for hop in xff:

                if src:
                    hops.append(("by", hop))
                    hops.append(("for", src))

                src = hop

            # The last address in X-Forward-For to the client address
            hops.append(("by", client_ip))
            hops.append(("for", src))

            # Final hop is to me
            hops.append(("by", my_ip))
            hops.append(("for", client_ip))

        else:
        
            hops.append(("by", my_ip))
            hops.append(("for", client_ip))

        hops = "&".join([
            urlencode({v[0]: v[1]}) for v in hops
        ])

        versions = [
            ("accounts-svc", "1.0.0"),
            ("accounts-web", self.config.get("client.version")),
        ]

        versions = "&".join([
            urlencode({v[0]: v[1]}) for v in versions
        ])

        product = "accountsmachine.io"
        now = datetime.datetime.utcnow().isoformat()[:-3] + "Z"

        # So in a cloud run environment, the client IP isn't client_ip
        # it's the an address in X-Forwared-For
        if len(xff) > 0:
                client_ip = xff[0]

        # Return headers
        return {
            'Gov-Client-Connection-Method': 'WEB_APP_VIA_SERVER',
            'Gov-Client-Browser-Do-Not-Track': dnt,
            'Gov-Client-Browser-JS-User-Agent': ua,
            'Gov-Client-Device-ID': dev_id,
            'Gov-Client-Multi-Factor': mfa,
            'Gov-Client-Public-IP': client_ip,
            'Gov-Client-Public-IP-Timestamp': now,
#            'Gov-Client-Public-Port': client_port,
            'Gov-Client-Screens': screens,
            'Gov-Client-Timezone': self.config.get("identity.device.tz"),
            'Gov-Client-User-IDs': user_ids,
            'Gov-Client-Window-Size': window,
            'Gov-Vendor-Forwarded': hops,
            'Gov-Vendor-License-IDs': '',
            'Gov-Vendor-Product-Name': quote_plus(product),
#            'Gov-Vendor-Public-IP': my_ip,
            'Gov-Vendor-Version': versions,
            'Authorization': 'Bearer %s' % self.auth.get("access_token"),
        }

class AuthEndpoint(auth.Auth):
    def __init__(self, auth):
        self.auth = auth
    def write(self):
        # Do nothing, we'll pick up the changed auth later.
        pass

class Vat:

    def __init__(self, config):

        self.client_id = config["vat-client-id"]
        self.client_secret = config["vat-client-secret"]
        self.redirect_uri = config["redirect-uri"]

    async def compute(self, state, renderer, id):

        try:
            html = await renderer.render(state, renderer, id, "vat")
        except Exception as e:
            html = ""
            logger.error(e)

        i = IxbrlProcess()
        vat = i.process(html)

        return vat

    async def get_vat_client(self, config, state, id):

        try:
            print(id)
            vauth = await state.vat_auth().get(id)
        except Exception as e:
            print(e, type(e))
        
            logger.error("No VAT auth stored")
            raise RuntimeError("No VAT auth stored.  "
                  "You should authenticate with the VAT service"
            )

        auth = AuthEndpoint(vauth)
        h = VatEndpoint(config, auth)

        # Refresh if needed.
        if "access_token" in auth.auth:
            old_token = auth.auth["access_token"]
        else:
            old_token = ""

        await auth.maybe_refresh(h)

        if  auth.auth["access_token"] != old_token:

            try:
                await state.vat_auth().put(company_number, auth.auth)
            except:
                await state.vat_auth().delete(company_number)

                raise RuntimeError("Failure to store refreshed token")

        return h

    async def get_status(self, config, state, id, start, end):

        cmp = await state.company().get(id)

        cli = await self.get_vat_client(config, state, id)

        l, p, o = await asyncio.gather(
            cli.get_vat_liabilities(cmp["vrn"], start, end),
            cli.get_vat_payments(cmp["vrn"], start, end),
            cli.get_obligations(cmp["vrn"], start, end),
        )

        return {
            "liabilities": [v.to_dict() for v in l],
            "payments": [v.to_dict() for v in p],
            "obligations": [v.to_dict() for v in o]
        }

    async def get_liabilities(self, config, state, id, start, end):
        cmp = await state.company().get(id)
        cli = await self.get_vat_client(config, state, id)
        l = await cli.get_vat_liabilities(cmp["vrn"], start, end)
        return [v.to_dict() for v in l]

    async def get_obligations(self, config, state, id, start, end):
        cmp = await state.company().get(id)
        cli = await self.get_vat_client(config, state, id)
        l = await cli.get_obligations(cmp["vrn"], start, end)
        return [v.to_dict() for v in l]

    async def get_open_obligations(self, config, state, id):
        cmp = await state.company().get(id)
        cli = await self.get_vat_client(config, state, id)
        l = await cli.get_open_obligations(cmp["vrn"])
        return [v.to_dict() for v in l]

    async def get_payments(self, config, state, id, start, end):
        cmp = await state.company().get(id)
        cli = await self.get_vat_client(config, state, id)
        l = await cli.get_vat_payments(cmp["vrn"], start, end)
        return [v.to_dict() for v in l]

    async def background_submit(
        self, user, email, config, state, renderer, id
    ):

        print(">>>>", id)
        log_stream = StringIO()
        sthislog = logging.StreamHandler(log_stream)
        thislog = logging.getLoggerClass()("vat")
        thislog.addHandler(sthislog)

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

                logger.debug("Submission of VAT config %s", id)

                cfg = await state.filing_config().get(id)

                cfg["state"] = "pending"
                await state.filing_config().put(id, cfg)

                logger.debug("VAT config %s", json.dumps(cfg))
                thislog.info("VAT config ID: %s", id)

                try:
                    company_number = cfg["company"]
                except Exception as e:
                    raise RuntimeError("No company number in configuration")

                cmp = await state.company().get(company_number)

                h = await self.get_vat_client(config, state, company_number)

                logger.debug("VRN is %s", cmp["vrn"])
                thislog.info("VRN is %s", cmp["vrn"])

                obs = await h.get_open_obligations(cmp["vrn"])

                logger.debug("Looking for obligation period due %s", cfg["due"])
                thislog.info("Period due %s", cfg["due"])

                obl = None
                for o in obs:
                    if str(o.due) == cfg["due"]: obl = o

                if obl is None:
                    raise RuntimeError(
                        "VAT due date %s not found in obligations" % cfg["due"]
                    )

                # Handle billing
                balance = await state.balance().get("balance")

                if balance["credits"]["vat"] < 1:
                        raise web.HTTPPaymentRequired(
                                text="No VAT credits available"
                        )

                balance["credits"]["vat"] -= 1
                balance["time"] = datetime.datetime.now().isoformat()

                transaction = {
                    "time": datetime.datetime.now().isoformat(),
                    "type": "filing",
                    "company": company_number,
                    "kind": "vat",
                    "filing": cfg["label"],
                    "id": id,
                    "email": email,
                    "uid": user,
                    "valid": True,
                    "order": {
                        "items": [
                            {
                                "kind": "vat",
                                "quantity": -1,
                            }
                        ]
                    }
                }

                tid = str(uuid.uuid4())

                await state.balance().put("balance", balance)
                await state.transaction().put(tid, transaction)

                # Billing written

                html = await renderer.render(
                    state, renderer, id, "vat"
                )

                i = IxbrlProcess()
                vat = i.process(html)

                await state.filing_report().put(id, html.encode("utf-8"))
                await state.filing_data().put(id, vat)

                rtn = model.Return()
                rtn.periodKey = obl.periodKey
                rtn.finalised = True
                rtn.vatDueSales = vat["VatDueSales"]
                rtn.vatDueAcquisitions = vat["VatDueAcquisitions"]
                rtn.totalVatDue = vat["TotalVatDue"]
                rtn.vatReclaimedCurrPeriod = vat["VatReclaimedCurrPeriod"]
                rtn.netVatDue = vat["NetVatDue"]
                rtn.totalValueSalesExVAT = vat["TotalValueSalesExVAT"]
                rtn.totalValuePurchasesExVAT = vat["TotalValuePurchasesExVAT"]
                rtn.totalValueGoodsSuppliedExVAT = vat["TotalValueGoodsSuppliedExVAT"]
                rtn.totalAcquisitionsExVAT = vat["TotalAcquisitionsExVAT"]

                thislog.info("VAT record:")
                for k, v in rtn.to_dict().items():
                    thislog.info("  %s: %s", k, v)

                thislog.info("Submitting VAT return...")
                await h.submit_vat_return(cmp["vrn"], rtn)
                thislog.info("Success.")

                await state.filing_status().put(id, {
                    "report": log_stream.getvalue()
                })

            except Exception as e:

                logger.debug("background_submit: Exception: %s", e)
                thislog.error("background_submit: Exception: %s", e)

                l = log_stream.getvalue()

                await state.filing_status().put(id, {
                    "report": l
                })

                await state.filing_report().put(id, "".encode("utf-8"))

                cfg = await state.filing_config().get(id)
                cfg["state"] = "errored"
                await state.filing_config().put(id, cfg)

                return

            cfg = await state.filing_config().get(id)
            cfg["state"] = "published"
            await state.filing_config().put(id, cfg)

        except Exception as e:

            logger.debug("background_submit: Exception: %s", e)

            try:
                await state.filing_status().put(id, {
                    "report": str(e)
                })
            except: pass

    async def submit(self, user, email, config, state, renderer, id):

        rec = state.filing_config().get(id)

        # Quick credit check before committing to background task
        balance = await state.balance().get("balance")

        if balance["credits"]["vat"] < 1:
                raise RuntimeError("No VAT credits available")

        print("____", id)

        asyncio.create_task(
                self.background_submit(user, email, config, state, renderer, id)
        )
