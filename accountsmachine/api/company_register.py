
import json
from aiohttp import web, ClientSession
import glob
import logging
import base64

logger = logging.getLogger("api.company-register")
logger.setLevel(logging.INFO)

class CompanyRegisterApi():

    def __init__(self, config):

        try:
            self.url = config["companies-service-url"]
        except:
            self.url = "https://api.company-information.service.gov.uk"

        print(self.url)

        key = config["companies-service-api-key"]
        self.auth = base64.b64encode(
            (key + ":").encode("utf-8")
        ).decode("utf-8")

        print(self.auth)

    async def get(self, request):

        request["auth"].verify_scope("ch-lookup")

        user = request["auth"].user

        try:

            id = request.match_info['id']

            logger.info("Lookup %s", id)

            if ".." in id:
                raise RuntimeError("Invalid id")

            async with ClientSession() as session:

                print(self.url)
                url = "https://api.company-information.service.gov.uk/"
                print(self.url)

                headers = {
                    "Authorization": "Basic " + self.auth
                }

                async with session.post(
                        self.url + "/company/" + id,
                        headers=headers
                ) as resp:

                    if resp.status != 200:
                        raise RuntimeError("Company lookup failed")

                    ci = await resp.json()

                async with session.post(
                        self.url + "/company/" + id + "/officers",
                        headers=headers
                ) as resp:

                    if resp.status != 200:
                        raise RuntimeError("Company lookup failed")

                    oi = await resp.json()

                logger.debug(ci)
                logger.debug(oi)

            return web.json_response({
                "company": ci,
                "officers": oi,
            })

        except Exception as e:
            logger.debug("Exception: %s", e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

