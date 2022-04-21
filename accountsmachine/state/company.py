
import logging

from . filing import Filing

logger = logging.getLogger("company")
logger.setLevel(logging.DEBUG)

class Company:

    def __init__(self, user, cid):
        self.user = user
        self.cid = cid

    async def get(self):
        return await self.user.company(self.cid).get()

    async def put(self, data):
        await self.user.company(self.cid).put(data)

    @staticmethod
    async def get_all(user):
        return await user.companies().list()

    async def delete(self):

        filings = self.user.filings()
        
        for fid in await filings.list():

            filing = await filings.filing(fid).get()

            if "company" in filing and filing["company"] == self.cid:

                await Filing(self.user, fid).delete()
                

        try:
            await self.user.company(self.cid).delete()
        except: pass

    async def put_logo(self, data, ctype):

        await self.user.company(self.cid).logo().put_image(data)
        await self.user.company(self.cid).logo().put({
            "content-type": ctype,
        })

    async def get_logo_type(self):
        try:
            info = await self.user.company(self.cid).logo().get()
            return info["content-type"]
        except Exception as e:
            raise KeyError
            

    async def get_logo(self):
        try:
            logo = await self.user.company(self.cid).logo().get_image()
            return logo
        except Exception as e:
            raise KeyError
