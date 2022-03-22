
class DocKind:
    def __init__(self, collection, state):
        self.collection = collection
        self.state = state
        self.store = state.store
        self.user = state.user
    def id(self, id):
        return id + "@" + self.user
    async def list(self):
        return await self.store.get_all(self.collection, "uid", self.user)
    async def get(self, id):
        return await self.store.get(self.collection, self.id(id))
    async def put(self, id, data):
        data["uid"] = self.user
        return await self.store.put(self.collection, self.id(id), data)
    async def delete(self, id):
        return await self.store.delete(self.collection, self.id(id))

class BlobKind:
    def __init__(self, collection, state, blob=False):
        self.collection = collection
        self.state = state
        self.store = state.store
        self.user = state.user
    def id(self, id):
        return id + "@" + self.user
    async def list(self):
        return await self.store.get_all(self.collection, "uid", self.user)
    async def get(self, id):
        obj = await self.store.get(self.collection, self.id(id))
        return obj["blob"]
    async def put(self, id, data):
        obj = {
            "uid": self.user,
            "blob": data
        }
        return await self.store.put(self.collection, self.id(id), obj)
    async def delete(self, id):
        return await self.store.delete(self.collection, self.id(id))

class State:
    def __init__(self, store, user):
        self.store = store
        self.user = user

    def doc(self, collection):
        return DocKind(collection, self)

    def blob(self, collection):
        return BlobKind(collection, self)

    def company(self):
        return self.doc("company")

    def filing_config(self):
        return self.doc("filing")

    def books(self):
        return self.blob("books")

    def booksinfo(self):
        return self.doc("booksinfo")

    def logo(self):
        return self.blob("logo")

    def signature(self):
        return self.blob("signature")

    def signatureinfo(self):
        return self.doc("signatureinfo")

    def logoinfo(self):
        return self.doc("logoinfo")

    def vat_auth(self):
        return self.doc("vat-auth")

    def corptax_auth(self):
        return self.doc("corptax-auth")

    def accounts_auth(self):
        return self.doc("accounts-auth")

    def filing_report(self):
        return self.blob("filing-report")

    def filing_data(self):
        return self.doc("filing-data")

    def filing_status(self):
        return self.doc("filing-status")

    def user_profile(self):
        return self.doc("user-profile")

