
import asyncio
from aiohttp import web
from aiohttp import ClientSession
from urllib.parse import urlencode, quote_plus
import uuid
import secrets
import datetime
import json
import os
import logging
from io import StringIO
import requests
import re
import time

from .. state import State
from .. ixbrl_process import IxbrlProcess

import gnucash_uk_vat.hmrc as hmrc
import gnucash_uk_vat.model as model
import gnucash_uk_vat.auth as auth

logger = logging.getLogger("api.vat")
logger.setLevel(logging.DEBUG)

def get_my_ip():

        # Cloud run services don't have a public IP
        return "0.0.0.0"

        # This works on normal machines
        import socket
        hostname = socket.gethostname()
        ip_address = socket.gethostbyname(hostname)
        return ip_address

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

class VatApi():
    def __init__(self, config, store):

        self.vat_auth_url = config["vat-auth-url"]
        self.vat_api_url = config["vat-api-url"]

        self.client_id = config["vat-client-id"]
        self.client_secret = config["vat-client-secret"]
        self.redirect_uri = config["redirect-uri"]

        self.store = store

        self.token_states = {}

        self.my_ip = get_my_ip()

    async def compute(self, request):

        request["auth"].verify_scope("vat")
        user = request["auth"].user

        try:

            id = request.match_info['id']

            try:
                html = await request["renderer"].render(
                    request["state"], request["renderer"],
                    id, "vat"
                )
            except Exception as e:
                html = ""
                logger.error(e)

            i = IxbrlProcess()
            vat = i.process(html)

            return web.json_response(vat)

        except Exception as e:

            logger.debug("compute: Exception: %s", e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )
        
    async def redirect_auth(self, request):

        request["auth"].verify_scope("vat")
        user = request["auth"].user

        id = request.match_info['id']

        url = self.vat_auth_url + "/oauth/authorize?"

        # FIXME: Well, this is OK for developing. Only handles one VAT
        # connection at once.
        # The fix would be to add to the token_states array, and expire old
        # values.
        state = secrets.token_hex(16)

        self.token_states = {
            state: {
                "user": user,
                "company": id
            }
        }

        url += urlencode({
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "state": state,
            "scope": "read:vat write:vat",
            "client_id": self.client_id
        })

        return web.json_response({
            "url": url
        })

    async def receive_token(self, request):

        code = request.query["code"]
        state = request.query["state"]

        if state not in self.token_states:
                raise web.HTTPUnauthorized(
                        text=json.dumps({
                                "message": "VAT token not valid",
                                "code": "vat-token-invalid"
                        }),
                        content_type="application/json"
                )

        user = self.token_states[state]["user"]
        company = self.token_states[state]["company"]

        try:

            async with ClientSession() as session:

                req = urlencode({
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.redirect_uri,
                    "code": code,
                    "state": state,
                })

                headers = {
                        'Content-Type': 'application/x-www-form-urlencoded',
                }

                async with session.post(self.vat_api_url + "/oauth/token",
                                        headers=headers, data=req) as resp:
                    token = await resp.json()

        except Exception as e:
            logger.info("receive_token: Exception: %s", e)
            raise web.HTTPInternalServerError(
                body="Failed to exchange code for token",
                content_type="text/plain"
            )

        state = State(self.store, user)

        now = datetime.datetime.utcnow()
        expires = now + datetime.timedelta(seconds=int(token["expires_in"]))
        expires = expires.replace(microsecond=0)
        expires = expires.isoformat()

        token["expires"] = expires
        
        await state.vat_auth().put(company, token)

        url = "/status/%s/vat" % company
        page = """
<html>
    <body>
        <h1>VAT authentication was successful</h1>
        <p>Click 
        <a href="%s">here</a>
        to return to the application.</p>
    </body>
</html>

""" % url

#        Return web.Response(body=page, content_type="text/html")
        return web.HTTPFound(url)

    async def background_submit(
            self, user, state, renderer, id, kind, request
    ):

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

                h = await self.get_vat_client(
                        user, company_number, state, request
                )

                cmp = await state.company().get(company_number)

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
                    "transaction": "use",
                    "company": company_number,
                    "kind": "vat",
                    "filing": cfg["label"],
                    "id": id,
                    "email": request["auth"].email,
                    "uid": request["auth"].user,
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
                    state, renderer, id, kind
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

    async def submit(self, request):

        request["auth"].verify_scope("vat")
        user = request["auth"].user

        try:

            id = request.match_info['id']
            kind = "vat"

            # Quick credit check before committing to background task
            balance = await request["state"].balance().get("balance")

            if balance["credits"]["vat"] < 1:
                    return web.HTTPPaymentRequired(
                            text="No VAT credits available"
                    )

            asyncio.create_task(
                self.background_submit(user, request["state"], 
                                       request["renderer"], id, kind, request)
            )

            return web.json_response()

        except Exception as e:

            logger.debug("submit: Exception: %s", e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    def get_vat_client_config(self, user, cmp, request):

        if "X-Device-ID" not in request.headers:
            raise RuntimeError("No device ID")

        if "X-Client-Version" not in request.headers:
            raise RuntimeError("No client version")

        if "X-Device-TZ" not in request.headers:
            raise RuntimeError("No timezone")

        host, port = request.transport.get_extra_info("peername")

        screen = json.loads(request.headers["X-Screen"])

        # The DNT header is deprecated
        dnt = "false"
        if "DNT" in request.headers and request.headers["DNT"] == "1":
                dnt = "true"

        # Get an parse X-Forwarded-For if it exists
        if "X-Forwarded-For" in request.headers:
            xff = request.headers["X-Forwarded-For"]
        elif "x-forwarded-for" in request.headers:
            xff = request.headers["x-forwarded-for"]
        else:
            xff = ""

        xff = xff.split(",")
        xff = [ v.strip() for v in xff ]
        xff = [v for v in filter(lambda x : x != "", xff)]

        return {
            "application.client-id": "ASD",
            "application.client-secret": "ASD",
            "client.version": request.headers["X-Client-Version"],
            "transport.forwarded": xff,
            "identity.vrn": "DUNNO",
            "identity.do-not-track": dnt,
            "identity.device.user-agent": request.headers["User-Agent"],
            "identity.device.id": request.headers["X-Device-ID"],
            "identity.device.tz": request.headers["X-Device-TZ"],
            "identity.transport.host": str(host),
            "identity.transport.port": str(port),
            "identity.user": request["auth"].user,
            "identity.email": request["auth"].email,
            "screen.width": screen[0],
            "screen.height": screen[1],
            "window.width": screen[2],
            "window.height": screen[3],
            "screen.colour-depth": screen[4],
            "screen.scaling-factor": screen[5],
            "server.ip": self.my_ip,
        }
    
    async def get_status(self, request):

        request["auth"].verify_scope("vat")
        user = request["auth"].user

        state = request["state"]

        try:

            id = request.match_info['id']
            start = request.query['start']
            end = request.query['end']

            start = datetime.date.fromisoformat(start)
            end = datetime.date.fromisoformat(end)

            # FIXME: Also called inside get_vat_client, too many reads
            cmp = await state.company().get(id)

            cli = await self.get_vat_client(user, id, state, request)

#            l = await cli.get_vat_liabilities(cmp["vrn"], start, end)
#            p = await cli.get_vat_payments(cmp["vrn"], start, end)
#            o = await cli.get_obligations(cmp["vrn"], start, end)

            l, p, o = await asyncio.gather(
                    cli.get_vat_liabilities(cmp["vrn"], start, end),
                    cli.get_vat_payments(cmp["vrn"], start, end),
                    cli.get_obligations(cmp["vrn"], start, end)
            )

            return web.json_response({
                "liabilities": [v.to_dict() for v in l],
                "payments": [v.to_dict() for v in p],
                "obligations": [v.to_dict() for v in o]
            })

        except Exception as e:

            logger.debug("get_status: Exception: %s", e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def get_liabilities(self, request):

        request["auth"].verify_scope("vat")
        user = request["auth"].user

        state = request["state"]

        try:

            id = request.match_info['id']
            start = request.query['start']
            end = request.query['end']

            start = datetime.date.fromisoformat(start)
            end = datetime.date.fromisoformat(end)

            # FIXME: Also called inside get_vat_client, too many reads
            cmp = await state.company().get(id)

            cli = await self.get_vat_client(user, id, state, request)

            liabs = await cli.get_vat_liabilities(cmp["vrn"], start, end)

            return web.json_response([v.to_dict() for v in liabs])            

        except Exception as e:

            logger.debug("get_liabilities: Exception: %s", e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def get_obligations(self, request):

        request["auth"].verify_scope("vat")
        user = request["auth"].user

        state = request["state"]

        try:

            id = request.match_info['id']
            start = request.query['start']
            end = request.query['end']

            start = datetime.date.fromisoformat(start)
            end = datetime.date.fromisoformat(end)

            # FIXME: Also called inside get_vat_client, too many reads
            cmp = await state.company().get(id)

            cli = await self.get_vat_client(user, id, state, request)

            ret = await cli.get_obligations(cmp["vrn"], start, end)

            return web.json_response([v.to_dict() for v in ret])            

        except Exception as e:

            logger.debug("get_obligations: Exception: %s", e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def get_open_obligations(self, request):

        request["auth"].verify_scope("vat")
        user = request["auth"].user

        state = request["state"]

        try:

            id = request.match_info['id']

            # FIXME: Also called inside get_vat_client, too many reads
            cmp = await state.company().get(id)

            cli = await self.get_vat_client(user, id, state, request)

            ret = await cli.get_open_obligations(cmp["vrn"])

            return web.json_response([v.to_dict() for v in ret])            

        except Exception as e:

            logger.debug("get_open_obligations: Exception: %s", e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def get_payments(self, request):

        request["auth"].verify_scope("vat")
        user = request["auth"].user

        state = request["state"]

        try:

            id = request.match_info['id']
            start = request.query['start']
            end = request.query['end']

            start = datetime.date.fromisoformat(start)
            end = datetime.date.fromisoformat(end)

            # FIXME: Also called inside get_vat_client, too many reads
            cmp = await state.company().get(id)

            cli = await self.get_vat_client(user, id, state, request)

            ret = await cli.get_vat_payments(cmp["vrn"], start, end)

            return web.json_response([v.to_dict() for v in ret])            

        except Exception as e:

            logger.debug("get_payments: Exception: %s", e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

    async def get_vat_client(self, user, company_number, state, request):

        cmp = await state.company().get(company_number)

        config = self.get_vat_client_config(user, cmp, request)

        config["vat-auth-url"] = self.vat_auth_url
        config["vat-api-url"] = self.vat_api_url

        try:
            vauth = await state.vat_auth().get(company_number)
        except:
            logger.error("No VAT auth stored")
            raise("No VAT auth stored.  "
                  "You should authenticate with the VAT service")

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

    async def deauthorize(self, request):

        request["auth"].verify_scope("vat")
        user = request["auth"].user

        state = request["state"]

        try:

            id = request.match_info['id']
            await state.vat_auth().delete(id)

            return web.Response()

        except Exception as e:

            logger.debug("deauthorize: Exception: %s", e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )
