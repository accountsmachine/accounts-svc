
class StateKind:
    def __init__(self, prefix, state, blob=False):
        self.prefix = prefix
        self.state = state
        self.store = state.store
        self.user = state.user
        self.blob = blob
    async def list(self):
        return await self.store.get_all(self.prefix + self.user)
    async def get(self, id):
        if self.blob:
            return await self.store.get_blob(self.prefix + self.user, id)
        else:
            return await self.store.get(self.prefix + self.user, id)
    async def put(self, id, data):
        if self.blob:
            return await self.store.put_blob(self.prefix + self.user, id, data)
        else:
            return await self.store.put(self.prefix + self.user, id, data)
    async def delete(self, id):
        return await self.store.delete(self.prefix + self.user, id)

class State:
    def __init__(self, store, user):
        self.store = store
        self.user = user

    def kind(self, prefix, blob=False):
        return StateKind(prefix, self, blob)

    def company(self):
        return self.kind("company-")

    def filing_config(self):
        return self.kind("filing-")

    def books(self):
        return self.kind("books-", blob=True)

    def booksinfo(self):
        return self.kind("booksinfo-")

    def logo(self):
        return self.kind("logo-", blob=True)

    def signature(self):
        return self.kind("signature-", blob=True)

    def signatureinfo(self):
        return self.kind("signatureinfo-")

    def logoinfo(self):
        return self.kind("logoinfo-")

    def vat_auth(self):
        return self.kind("vat-auth-")

    def corptax_auth(self):
        return self.kind("corptax-auth-")

    def accounts_auth(self):
        return self.kind("accounts-auth-")

    def filing_report(self):
        return self.kind("filing-report-", blob=True)

    def filing_data(self):
        return self.kind("filing-data-")

    def filing_status(self):
        return self.kind("filing-status-")

