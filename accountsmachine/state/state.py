
import base64

# Security target: Make sure the caller can't change the uid in other people's
# data in order to take over.
class DocKind:
    def __init__(self, collection, state):
        self.collection = collection
        self.state = state
        self.store = state.store.docstore
        self.user = state.user
        self.tx = None
    def id(self, id):
        return id + "@" + self.user
    async def list(self):
        data = await self.store.get_all(self.collection, "uid", self.user)
        data = {v: data[v]["data"] for v in data}
        return  data
    async def get(self, id):
        data = await self.store.get(self.collection, self.id(id), tx=self.tx)
        return data["data"]
    async def put(self, id, data):
        data = {
            "uid": self.user,
            "data": data
        }
        return await self.store.put(self.collection, self.id(id), data)
    async def delete(self, id):
        return await self.store.delete(self.collection, self.id(id))

class BlobKind:
    def __init__(self, collection, state, blob=False):
        self.collection = collection
        self.state = state
        self.store = state.store.blobstore
        self.user = state.user
    def id(self, id):
        return self.user + "/" + id + "/" + self.collection
    async def list(self):
        raise RuntimeError("Not implemented")
    async def get(self, id):
        obj = await self.store.get(self.id(id))
        return base64.b64decode(obj["blob"])
    async def put(self, id, data):
        obj = {
            "uid": self.user,
            "blob": base64.b64encode(data).decode("utf-8")
        }
        return await self.store.put(self.id(id), obj)
    async def delete(self, id):
        return await self.store.delete(self.id(id))

class StateTx:
    def __init__(self):
        pass

    def get_tx(self, val):
        return self.tx
        
    def __getattr__(self, val):

        if not hasattr(self.state, val):
            raise RuntimeError("Collection " + val + " not known.")

        mthd = getattr(self.state, val)

        def thing():
            obj = mthd()

            # Hackery.  Put transaction in the DocKind object.
            if isinstance(obj, DocKind):
                obj.transaction = self.tx

            return obj

        return thing

class DocObject:
    async def get(self):
        ref = await self.doc.get()
        if not ref.exists:
            raise KeyError()
        return ref.to_dict()
    async def put(self, obj):
        await self.doc.set(obj)
#    async def update(self, obj):
#        await self.doc.set(obj)
    async def delete(self):
        await self.doc.delete()

class CollObject:
    async def list(self):
        all = await self.coll.get()
        return {v.id: v.to_dict() for v in all}
        
class User(DocObject):
    def __init__(self, store, uid):
        self.store = store
        self.doc = store.collection("users").document(uid)

    def company(self, cid):
        return Company(self.store, self.doc, cid)

    def filing(self, fid):
        return Filing(self.store, user.doc, fid)

    def companies(self):
        return Companies(self.store, self.doc)

class Companies(CollObject):
    def __init__(self, store, userdoc):
        self.store = store
        self.coll = userdoc.collection("companies")

class Company(DocObject):
    def __init__(self, store, userdoc, cid):
        self.store = store
        self.doc = userdoc.collection("companies").document(cid)
    def vat_auth(self):
        return VatAuth(self.store, self.doc)
    def vat_auth_placeholder(self):
        return VatAuthPlaceholder(self.store, self.doc)
    def corptax_auth(self):
        return CorptaxAuth(self.store, self.doc)
    def accounts_auth(self):
        return AccountsAuth(self.store, self.doc)

class VatAuth(DocObject):
    def __init__(self, store, doc):
        self.store = store
        self.doc = doc.collection("auth").document("vat")

class VatAuthPlaceholder(DocObject):
    def __init__(self, store, doc):
        self.store = store
        self.doc = doc.collection("auth").document("vat-placeholder")

class CorptaxAuth(DocObject):
    def __init__(self, store, doc):
        self.store = store
        self.doc = doc.collection("auth").document("corptax")

class AccountsAuth(DocObject):
    def __init__(self, store, doc):
        self.store = store
        self.doc = doc.collection("auth").document("accounts")

class Filing(DocObject):
    def __init__(self, store, userdoc, fid):
        self.store = store
        self.doc = userdoc.collection("filings").document(fid)

class State:
    def __init__(self, store):
        self.store = store

    def user(self, uid):
        return User(self.store, uid)





    def create_transaction(self):
        t = StateTx()
        t.state = self
        t.tx = self.store.docstore.db.transaction()
        return t

    # def doc(self, collection):
    #     return DocKind(collection, self)

    # def blob(self, collection):
    #     return BlobKind(collection, self)




    # def company(self):
    #     return self.doc("company")

    # def subscription(self):
    #     return self.doc("subscription")

    # def filing_config(self):
    #     return self.doc("filing")

    # def books(self):
    #     return self.blob("books")

    # def booksinfo(self):
    #     return self.doc("booksinfo")

    # def balance(self):
    #     return self.doc("balance")

    # def transaction(self):
    #     return self.doc("transaction")

    # def logo(self):
    #     return self.blob("logo")

    # def signature(self):
    #     return self.blob("signature")

    # def signature_info(self):
    #     return self.doc("signature-info")

    # def logoinfo(self):
    #     return self.doc("logoinfo")

    # def vat_auth(self):
    #     return self.doc("vat-auth")

    # def corptax_auth(self):
    #     return self.doc("corptax-auth")

    # def accounts_auth(self):
    #     return self.doc("accounts-auth")

    # def filing_report(self):
    #     return self.blob("filing-report")

    # def filing_data(self):
    #     return self.doc("filing-data")

    # def filing_status(self):
    #     return self.doc("filing-status")

    # def user_profile(self):
    #     return self.doc("user-profile")

    # def books_mapping(self):
    #     return self.doc("books-mapping")

    # def vat_auth_ref(self):
    #     return self.doc("vat-auth-ref")
