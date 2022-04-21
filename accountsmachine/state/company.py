
import logging

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

        # FIXME: Broken
        for fid in await self.user.filing_config().list():

            filing = await self.user.filing_config().get(fid)

            if "company" in filing and filing["company"] == self.cid:

                try:
                    await self.user.filing_report().delete(fid)
                except:
                    pass

                try:
                    await self.user.filing_data().delete(fid)
                except:
                    pass

                try:
                    await self.user.filing_status().delete(fid)
                except:
                    pass

                try:
                    await self.user.signature_info().delete(fid)
                except:
                    pass

                try:
                    await self.user.signature().delete(fid)
                except:
                    pass

                await self.user.filing_config().delete(fid)

        try:
            await self.user.books().delete(self.cid)
        except: pass

        try:
            await self.user.books_mapping().delete(self.cid)
        except: pass

        try:
            await self.user.booksinfo().delete(self.cid)
        except: pass

        try:
            await self.user.logo().delete(self.cid)
        except: pass

        try:
            await self.user.logoinfo().delete(self.cid)
        except: pass

        try:
            await self.user.vat_auth().delete(self.cid)
        except: pass

        try:
            await self.user.corptax_auth().delete(self.cid)
        except: pass

        try:
            await self.user.accounts_auth().delete(self.cid)
        except: pass

        try:
            await self.user.company().delete(self.cid)
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
