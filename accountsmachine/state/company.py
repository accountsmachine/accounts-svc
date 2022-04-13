
import json
from aiohttp import web
import aiohttp
import glob
import logging

logger = logging.getLogger("company")
logger.setLevel(logging.DEBUG)

class Company:
    def __init__(self, state, id):
        self.state = state
        self.id = id
    async def get(self):
        return await self.state.company().get(self.id)
    async def put(self, data):
        await self.state.company().put(self.id, data)

    @staticmethod
    async def get_all(state):
        return await state.company().list()

    async def delete(self):

        for fid in await self.state.filing_config().list():

            filing = await self.state.filing_config().get(fid)

            if "company" in filing and filing["company"] == self.id:

                try:
                    await self.state.filing_report().delete(fid)
                except:
                    pass

                try:
                    await self.state.filing_data().delete(fid)
                except:
                    pass

                try:
                    await self.state.filing_status().delete(fid)
                except:
                    pass

                try:
                    await self.state.signature_info().delete(fid)
                except:
                    pass

                try:
                    await self.state.signature().delete(fid)
                except:
                    pass

                await self.state.filing_config().delete(fid)

        try:
            await self.state.books().delete(self.id)
        except: pass

        try:
            await self.state.books_mapping().delete(self.id)
        except: pass

        try:
            await self.state.booksinfo().delete(self.id)
        except: pass

        try:
            await self.state.logo().delete(self.id)
        except: pass

        try:
            await self.state.logoinfo().delete(self.id)
        except: pass

        try:
            await self.state.vat_auth().delete(self.id)
        except: pass

        try:
            await self.state.corptax_auth().delete(self.id)
        except: pass

        try:
            await self.state.accounts_auth().delete(self.id)
        except: pass

        try:
            await self.state.company().delete(self.id)
        except: pass

        return web.Response()

    async def put_logo(self, data, ctype):
        await self.state.logo().put(self.id, data)
        await self.state.logoinfo().put(self.id, {
            "content-type": ctype,
        })

    async def get_logo_type(self):
        try:
            info = await self.state.logoinfo().get(self.id)
            return info["content-type"]
        except:
            raise KeyError
            

    async def get_logo(self):
        try:
            logo = await self.state.logo().get(self.id)
            return logo
        except:
            raise KeyError
