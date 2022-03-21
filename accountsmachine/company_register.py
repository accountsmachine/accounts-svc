
import json
from aiohttp import web
import glob
import logging

logger = logging.getLogger("company-register")
logger.setLevel(logging.DEBUG)

class CompanyRegister():

    def __init__(self):
#        self.db = json.loads(open("companies.json").read())
        self.db = {}

    async def get(self, request):

        request["auth"].verify_scope("ch-lookup")
        user = request["auth"].user

        try:

            id = request.match_info['id']

            logger.info("Lookup %s", id)

            if ".." in id:
                raise RuntimeError("Invalid id")

            if id not in self.db:
                return web.HTTPNotFound()

            return web.json_response(self.db[id])

        except Exception as e:
            print("Exception: %s", e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )

