
import json
from aiohttp import web
import glob
import logging

logger = logging.getLogger("state.filing")
logger.setLevel(logging.DEBUG)

class Filing():

    def __init__(self, state, id):
        self.state = state
        self.id = id

    async def get(self):
        return await self.state.filing_config().get(self.id)
    async def put(self, data):
        await self.state.filing_config().put(self.id, data)

    @staticmethod
    async def get_all(state):
        return await state.filing_config().list()

    async def delete(self):

        try:
            await self.state.filing_report().delete(self.id)
        except: pass

        try:
            await self.state.filing_data().delete(self.id)
        except: pass

        try:
            await self.state.filing_status().delete(self.id)
        except: pass

        try:
            await self.state.signature_info().delete(self.id)
        except: pass

        try:
            await self.state.signature().delete(self.id)
        except: pass

        await self.state.filing_config().delete(self.id)

    async def put_signature(self, img, ctype):

        await self.state.signature().put(self.id, img)
        await self.state.signature_info().put(self.id, {
            "content-type": ctype,
        })

    async def get_signature(self):

        info = await self.state.signature_info().get(self.id)
        ctype = info["content-type"]

        img = await self.state.signature().get(self.id)

        return img, ctype

    async def get_report(self):
        return await self.state.filing_report().get(self.id)

    async def get_data(self):
        return await self.state.filing_data().get(self.id)

    async def get_status(self):
        return await self.state.filing_status().get(self.id)

    async def set_state(self, state):

        cfg = self.get()

        if "state" in cfg:
            if cfg["state"] in ["errored", "pending"]:
                cfg["state"] = state
            else:
                raise RuntimeError("Not OK")
        else:
            raise RuntimeError("Not OK")

        await self.put(cfg)

