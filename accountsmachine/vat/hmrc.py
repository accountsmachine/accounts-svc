
import datetime
from urllib.parse import urlencode, quote_plus
import logging
import asyncio

logger = logging.getLogger("vat.hmrc")
logger.setLevel(logging.DEBUG)

import gnucash_uk_vat.hmrc as hmrc
import gnucash_uk_vat.auth as auth

from importlib import metadata
try:
    version = metadata.version("accounts-svc")
except:
    version = "local"

logger.info("accounts-svc version is: %s", version)

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
            ("accounts-svc", version),
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
        hdrs = {
            'Gov-Client-Connection-Method': 'WEB_APP_VIA_SERVER',
            'Gov-Client-Browser-Do-Not-Track': dnt,
            'Gov-Client-Browser-JS-User-Agent': ua,
            'Gov-Client-Device-ID': dev_id,
#            'Gov-Client-Multi-Factor': mfa,
            'Gov-Client-Public-IP': client_ip,
            'Gov-Client-Public-IP-Timestamp': now,
#            'Gov-Client-Public-Port': client_port,
            'Gov-Client-Screens': screens,
            'Gov-Client-Timezone': self.config.get("identity.device.tz"),
            'Gov-Client-User-IDs': user_ids,
            'Gov-Client-Window-Size': window,
#            'Gov-Vendor-Forwarded': hops,
#            'Gov-Vendor-License-IDs': '',
            'Gov-Vendor-Product-Name': quote_plus(product),
#            'Gov-Vendor-Public-IP': my_ip,
            'Gov-Vendor-Version': versions,
            'Authorization': 'Bearer %s' % self.auth.get("access_token"),
        }

        # print("")
        # print("")
        # print("")
        # for k, v in hdrs.items():
        #     print("   ", k)
        #     print("       ", v)
        # print("")

        return hdrs

class AuthEndpoint(auth.Auth):
    def __init__(self, auth):
        self.auth = auth
    def write(self):
        # Do nothing, we'll pick up the changed auth later.
        pass

class Hmrc:

    def __init__(self, config, auth, vrn):
        self.config = config
        self.auth = auth
        self.vrn = vrn

    async def get_vat_client(self):

        try:
            vauth = await self.auth.get()
        except Exception as e:
            logger.error(e)
            logger.error("No VAT auth stored")
            raise RuntimeError("No VAT auth stored.  "
                  "You should authenticate with the VAT service"
            )

        auth = AuthEndpoint(vauth)
        h = VatEndpoint(self.config, auth)

        # Refresh if needed.
        if "access_token" in auth.auth:
            old_token = auth.auth["access_token"]
        else:
            old_token = ""

        await auth.maybe_refresh(h)

        if  auth.auth["access_token"] != old_token:

            try:
                await self.auth.put(auth.auth)
            except:
                await self.auth.delete()
                raise RuntimeError("Failure to store refreshed token")

        return h

    async def get_vat_payments_workaround(self, cli, start, end):

        try:
            return await cli.get_vat_payments(self.vrn, start, end)
        except:
            # Works around a broken sandbox
            return []

    async def get_vat_liabilities_workaround(self, cli, start, end):

        try:
            return await cli.get_vat_liabilities(self.vrn, start, end)
        except:

            # Works around a broken sandbox
            return []

    async def get_obligations_workaround(self, cli, start, end):

        # Try the normal service
        try:
            obls = await cli.get_obligations(self.vrn, start, end)

            obls = [
                v for v in obls
                if (
                        (v.start > start and v.start < end) or
                        (v.end > start and v.end < end)
                )
            ]


            return obls
        except:

            # Failed, fall through to the sandbox work-around
            pass

        # But the sandbox is broken?  So get open obligations are report
        # those.
        obls = await cli.get_open_obligations(self.vrn)
        
        obls = [
            v for v in obls
            if (
                    (v.start > start and v.start < end) or
                    (v.end > start and v.end < end)
            )
        ]

        return obls

    async def get_status(self, start, end):

        cli = await self.get_vat_client()

        return await asyncio.gather(
            self.get_vat_liabilities_workaround(cli, start, end),
            self.get_vat_payments_workaround(cli, start, end),
            self.get_obligations_workaround(cli, start, end),
        )

    async def get_liabilities(self, start, end):

        cli = await self.get_vat_client()

        return await cli.get_vat_liabilities(self.vrn, start, end)

    async def get_obligations(self, start, end):

        cli = await self.get_vat_client()

        return await cli.get_obligations(self.vrn, start, end)

    async def get_open_obligations(self):

        cli = await self.get_vat_client()

        obls = await cli.get_open_obligations(self.vrn)
        return obls

    async def get_payments(self, start, end):

        cli = await self.get_vat_client()

        return await cli.get_vat_payments(self.vrn, start, end)

    async def submit_vat_return(self, rtn):

        cli = await self.get_vat_client()

        await cli.submit_vat_return(self.vrn, rtn)

