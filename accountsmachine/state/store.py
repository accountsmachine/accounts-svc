
import json
import logging

from google.cloud import storage
from firebase_admin import firestore

logger = logging.getLogger("store")
logger.setLevel(logging.DEBUG)

class Collection:
    def __init__(self, db, collection):
        self.db = db
        self.collection = db.collection(collection)
    def __setitem__(self, key, item):
        self.collection.document(key).set(item)
    def __getitem__(self, key):
        doc = self.collection.document(key).get()
        if not doc.exists:
            raise KeyError()
        return doc.to_dict()
    def __delitem__(self, key):
        self.collection.document(key).delete()
    def all(self, key, value):
        docs = [v for v in self.collection.where(key, '==', value).stream()]
        return {
            doc.id.split("@")[0]: doc.to_dict()
            for doc in docs
        }

class DocStore:
    def __init__(self, config, firebase):

        logger.debug("Opening firestore...")
        self.db = firestore.client()
        logger.debug("Opened")

    def collection(self, coll):
        return Collection(self.db, coll)

    async def get(self, coll, id):
        logger.debug("get %s %s" % (coll, id))
        return self.collection(coll)[id]

    async def put(self, coll, id, data):
        logger.debug("put %s %s" % (coll, id))
        self.collection(coll)[id] = data

    async def delete(self, coll, id):
        logger.debug("delete %s %s" % (coll, id))
        del self.collection(coll)[id]

    async def get_all(self, coll, key, value):
        logger.debug("get_all %s" % coll)
        data = self.collection(coll).all(key, value)
        return data

class BlobStore:
    def __init__(self, config, firebase):

        logger.debug("Opening blobstore...")
        self.db = storage.Client.from_service_account_json(
            config["svc-account-key"]
        )

        self.bucket = self.db.bucket(config["bucket"])
        logger.debug("Opened")

    async def get(self, id):
        logger.debug("get %s" % (id))
        blob = self.bucket.blob(id)
        return json.loads(blob.download_as_string())

    async def put(self, id, data):
        logger.debug("put %s" % (id))
        blob = self.bucket.blob(id)
        strm = json.dumps(data).encode("utf-8")
        blob.upload_from_string(strm)

    async def delete(self, id):
        logger.debug("delete %s" % (id))
        blob = self.bucket.blob(id)
        blob.delete()

class Store:
    def __init__(self, config, firebase):

        logger.debug("Opening stores...")
        self.docstore = DocStore(config, firebase)
        self.blobstore = BlobStore(config, firebase)
        logger.debug("Opened")

