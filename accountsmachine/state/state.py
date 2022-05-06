
import base64
import logging

logger = logging.getLogger("state.state")
logger.setLevel(logging.INFO)

# Security target: Make sure the caller can't change the uid in other people's
# data in order to take over.

class DocObject:
    def __init__(self, store, tx=None):
        self.store = store
        self.tx = tx
    async def get(self):
        ref = await self.doc.get(transaction=self.tx)
        if not ref.exists:
            raise KeyError()
        return ref.to_dict()
    async def put(self, obj):
        await self.doc.set(obj)
#    async def update(self, obj):
#        await self.doc.set(obj)
    async def delete(self):
        await self.doc.delete()
    def create_transaction(self):
        return self.store.docstore.db.transaction()
    def use_transaction(self, tx):
        self.tx = tx

class CollObject:
    async def list(self):
        all = await self.coll.get()
        return {v.id: v.to_dict() for v in all}
        
class User(DocObject):
    def __init__(self, store, uid):
        super().__init__(store)
        self.uid = uid
        self.doc = store.collection("users").document(uid)

    def companies(self):
        return Companies(self, self.store, self.doc)

    def company(self, cid):
        return Company(self, self.store, self.doc, cid)

    def filings(self):
        return Filings(self, self.store, self.doc)

    def filing(self, fid):
        return Filing(self, self.store, self.doc, fid)

    def credits(self, id=None):
        return Credits(self, self.store, self.doc, id)

    def transactions(self):
        return Transactions(self, self.store, self.doc)

    def transaction(self, tid):
        return Transaction(self, self.store, self.doc, tid)

    def packages(self):
        return Packages(self, self.store, self.doc)

    def package(self, id):
        return Package(self, self.store, self.doc, id)

    def currentpackage(self):
        return CurrentPackage(self, self.store, self.doc)

    async def delete(self):

        logger.info("Deleting user %s", self.uid)

        # Delete companies
        try:
            ids = await self.companies().list()
            ids = ids.keys()

            for id in ids:
                try:
                    logger.info("Deleting company %s", id)
                    await self.company(id).delete()
                except: pass
        except:
            pass

        # Delete filings
        try:
            ids = await self.filings().list()
            ids = ids.keys()

            for id in ids:
                try:
                    logger.info("Deleting filing %s", id)
                    await self.filing(id).delete()
                except: pass
        except:
            pass

        # Delete transactions
        try:
            ids = await self.transactions().list()
            ids = ids.keys()

            for id in ids:
                try:
                    logger.info("Deleting tx %s", id)
                    await self.transaction(id).delete()
                except: pass
        except:
            pass

        try:
            logger.info("Deleting current package")
            await self.currentpackage().delete()
        except: pass

        # Delete packages
        try:
            ids = await self.packages().list()
            ids = ids.keys()

            for id in ids:
                try:
                    logger.info("Deleting package %s", id)
                    await self.package(id).delete()
                except Exception as e:
                    print(e)

        except Exception as e:
            print(e)

        try:
            logger.info("Deleting credits")
            await self.credits().delete()
        except: pass

        logger.info("Deleting user object")
        await super().delete()

class Credits(DocObject):
    def __init__(self, user, store, doc, id):
        super().__init__(store)
        self.user = user
        if id == None:
            id = "balance"
            self.doc = doc.collection("credits").document(id)
        else:
            self.doc = self.store.docstore.db.collection("users").document(id)

class Companies(CollObject):
    def __init__(self, user, store, userdoc):
        self.user = user
        self.store = store
        self.coll = userdoc.collection("companies")
        self.doc = userdoc
    def company(self, cid):
        return Company(self.user, self.store, self.doc, cid)

class Company(DocObject):
    def __init__(self, user, store, userdoc, cid):
        super().__init__(store)
        self.user = user
        self.cid = cid
        self.doc = userdoc.collection("companies").document(cid)
    def vat_auth(self):
        return VatAuth(self.store, self.doc)
    def vat_auth_placeholder(self):
        return VatAuthPlaceholder(self.store, self.doc)
    def corptax_auth(self):
        return CorptaxAuth(self.store, self.doc)
    def accounts_auth(self):
        return AccountsAuth(self.store, self.doc)
    def books_mapping(self):
        return BooksMapping(self.store, self.doc)
    def books(self):
        return Books(self, self.store, self.doc)
    def logo(self):
        return Logo(self, self.store, self.doc)
    async def delete(self):

        try:
            await self.books().delete()
        except: pass

        try:
            await self.logo().delete()
        except: pass

        try:
            await self.vat_auth().delete()
        except: pass

        try:
            await self.vat_auth_placeholder().delete()
        except: pass

        try:
            await self.books_mapping().delete()
        except: pass

        try:
            await self.corptax_auth().delete()
        except: pass

        try:
            await self.accounts_auth().delete()
        except: pass

        await super().delete()

class VatAuth(DocObject):
    def __init__(self, store, doc):
        super().__init__(store)
        self.doc = doc.collection("auth").document("vat")

class VatAuthPlaceholder(DocObject):
    def __init__(self, store, doc):
        super().__init__(store)
        self.doc = doc.collection("auth").document("vat-placeholder")

class CorptaxAuth(DocObject):
    def __init__(self, store, doc):
        super().__init__(store)
        self.doc = doc.collection("auth").document("corptax")

class AccountsAuth(DocObject):
    def __init__(self, store, doc):
        super().__init__(store)
        self.doc = doc.collection("auth").document("accounts")

class Filings(CollObject):
    def __init__(self, user, store, userdoc):
        self.user = user
        self.store = store
        self.coll = userdoc.collection("filings")
        self.doc = userdoc
    def filing(self, fid):
        return Filing(self.user, self.store, self.doc, fid)

class Filing(DocObject):
    def __init__(self, user, store, userdoc, fid):
        super().__init__(store)
        self.user = user
        self.doc = userdoc.collection("filings").document(fid)
        self.fid = fid

    def get_report_store_id(self):
        return self.user.uid + "/f/" + self.fid + "/report"

    def status(self):
        return FilingStatus(self.store, self.doc)

    def data(self):
        return FilingData(self.store, self.doc)

    def signature(self):
        return Signature(self, self.store, self.doc)

    async def get_report(self):
        sid = self.get_report_store_id()
        obj = await self.store.blobstore.get(sid)
        return base64.b64decode(obj["blob"])

    async def put_report(self, data):
        sid = self.get_report_store_id()
        obj = {
            "blob": base64.b64encode(data).decode("utf-8")
        }
        return await self.store.blobstore.put(sid, obj)

    async def delete(self):
        try:
            await self.signature().delete()
        except: pass
        try:
            await self.status().delete()
        except: pass
        try:
            await self.data().delete()
        except: pass
        try:
            await self.delete_report()
        except: pass
        await super().delete()
        

    async def delete_report(self):
        sid = self.get_report_store_id()
        await self.store.blobstore.delete(sid)

class FilingStatus(DocObject):
    def __init__(self, store, doc):
        super().__init__(store)
        self.doc = doc.collection("output").document("status")

class FilingData(DocObject):
    def __init__(self, store, doc):
        super().__init__(store)
        self.doc = doc.collection("output").document("data")

class Transactions(CollObject):
    def __init__(self, user, store, userdoc):
        self.user = user
        self.store = store
        self.coll = userdoc.collection("transactions")
        self.doc = userdoc
    def transaction(self, tid):
        return Transaction(self.user, self.store, self.doc, tid)

class Transaction(DocObject):
    def __init__(self, user, store, userdoc, tid):
        super().__init__(store)
        self.user = user
        self.tid = tid
        self.doc = userdoc.collection("transactions").document(tid)

class BooksMapping(DocObject):
    def __init__(self, store, doc):
        super().__init__(store)
        self.doc = doc.collection("books").document("mapping")

class Books(DocObject):
    def __init__(self, company, store, doc):
        super().__init__(store)
        self.company = company
        self.doc = doc.collection("books").document("info")
    def get_store_id(self):
        return self.company.user.uid + "/c/" + self.company.cid + "/books"

    async def get_accounts(self):
        sid = self.get_store_id()
        obj = await self.store.blobstore.get(sid)
        return base64.b64decode(obj["blob"])

    async def put_accounts(self, data):
        sid = self.get_store_id()
        obj = {
            "blob": base64.b64encode(data).decode("utf-8")
        }
        return await self.store.blobstore.put(sid, obj)

    async def delete(self):
        sid = self.get_store_id()
        try:
            await self.store.blobstore.delete(sid)
        except: pass
        try:
            await super().delete()
        except: pass

class Logo(DocObject):
    def __init__(self, company, store, doc):
        super().__init__(store)
        self.company = company
        self.doc = doc.collection("logo").document("info")
    def get_store_id(self):
        return self.company.user.uid + "/c/" + self.company.cid + "/logo"

    async def get_image(self):
        sid = self.get_store_id()
        obj = await self.store.blobstore.get(sid)
        return base64.b64decode(obj["blob"])

    async def put_image(self, data):
        sid = self.get_store_id()
        obj = {
            "blob": base64.b64encode(data).decode("utf-8")
        }
        return await self.store.blobstore.put(sid, obj)

    async def delete(self):
        sid = self.get_store_id()
        try:
            await self.store.blobstore.delete(sid)
        except: pass
        try:
            await super().delete()
        except: pass

class Signature(DocObject):
    def __init__(self, filing, store, doc):
        super().__init__(store)
        self.filing = filing
        self.doc = doc.collection("signature").document("info")
    def get_store_id(self):
        return self.filing.user.uid + "/f/" + self.filing.fid + "/signature"

    async def get_image(self):
        sid = self.get_store_id()
        obj = await self.store.blobstore.get(sid)
        return base64.b64decode(obj["blob"])

    async def put_image(self, data):
        sid = self.get_store_id()
        obj = {
            "blob": base64.b64encode(data).decode("utf-8")
        }
        return await self.store.blobstore.put(sid, obj)

    async def delete(self):
        sid = self.get_store_id()
        try:
            await self.store.blobstore.delete(sid)
        except: pass
        await super().delete()

class Packages(CollObject):
    def __init__(self, user, store, userdoc):
        self.user = user
        self.store = store
        self.coll = userdoc.collection("packages")
        self.doc = userdoc
    def package(self, id):
        return Package(self.user, self.store, self.doc, id)

# Don't really use the package records, just a history.
class Package(DocObject):
    def __init__(self, user, store, userdoc, id):
        super().__init__(store)
        self.user = user
        self.id = id
        self.doc = userdoc.collection("packages").document(id)

# Package IDs are uppercase.  There is a special 'current' package.
class CurrentPackage(DocObject):
    def __init__(self, user, store, userdoc):
        super().__init__(store)
        self.user = user
        self.id = id
        self.doc = userdoc.collection("packages").document("current")

class Log(DocObject):
    def __init__(self, store, id):
        super().__init__(store)
        self.id = id
        self.doc = store.collection("log").document(id)

class State:
    def __init__(self, store):
        self.store = store

    def user(self, uid):
        return User(self.store, uid)

    def log(self, id):
        return Log(self.store, id)

