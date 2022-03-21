
import json
from aiohttp import web, ClientSession
import glob
import logging
import base64

logger = logging.getLogger("company-register")
logger.setLevel(logging.DEBUG)

class CompanyRegister():

    def __init__(self, config):

        key = config["companies-house-api-key"]

        self.auth = base64.b64encode(
            (key + ":").encode("utf-8")
        ).decode("utf-8")

    async def get(self, request):

        request["auth"].verify_scope("ch-lookup")

        user = request["auth"].user

        try:

            id = request.match_info['id']

            logger.info("Lookup %s", id)

            if ".." in id:
                raise RuntimeError("Invalid id")

            async with ClientSession() as session:

                url = "https://api.company-information.service.gov.uk/"
                

                headers = {
                    "Authorization": "Basic " + self.auth
                }

                async with session.post(
                        url + "/company/" + id,
                        headers=headers
                ) as resp:

                    if resp.status != 200:
                        raise RuntimeError("Company lookup failed")

                    ci = await resp.json()

                async with session.post(
                        url + "/company/" + id + "/officers",
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

