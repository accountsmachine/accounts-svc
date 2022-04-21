
import logging

logger = logging.getLogger("state.filing")
logger.setLevel(logging.DEBUG)

class Filing():

    def __init__(self, user, fid):
        self.user = user
        self.fid = fid

    async def get(self):
        return await self.user.filing(self.fid).get()

    async def put(self, data):
        await self.user.filing(self.fid).put(data)

    @staticmethod
    async def get_all(user):
        return await user.filings().list()

    async def delete(self):

        # FIXME: BROKEN
        try:
            await self.user.filing(self.fid).delete()
        except: pass

        try:
            await self.user.signature_info().delete(self.fid)
        except: pass

        try:
            await self.user.signature().delete(self.fid)
        except: pass

        await self.user.filing(self.fid).delete()

    async def put_signature(self, img, ctype):

        await self.user.signature().put(self.fid, img)
        await self.user.signature_info().put(self.fid, {
            "content-type": ctype,
        })

    async def get_signature(self):

        info = await self.user.signature_info().get(self.fid)
        ctype = info["content-type"]

        img = await self.user.signature().get(self.fid)

        return img, ctype

    async def get_report(self):
        return await self.user.filing(self.fid).get_report()

    async def get_data(self):
        return await self.user.filing(self.fid).data().get()

    async def get_status(self):
        return await self.user.filing(self.fid).status().get()

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

