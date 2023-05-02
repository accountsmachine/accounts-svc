
import json
import logging

from google.cloud import storage
from firebase_admin import firestore

logger = logging.getLogger("store")
logger.setLevel(logging.DEBUG)

class DocCollection:
    def __init__(self, db, collection):
        self.db = db
        self.collection = db.collection(collection)
    async def set(self, key, item):
        await self.collection.document(key).set(item)
    async def get(self, key, tx=None):
        doc = await self.collection.document(key).get(transaction=tx)
        if not doc.exists:
            raise KeyError()
        return doc.to_dict()
    async def delete(self, key):
        await self.collection.document(key).delete()
    async def all(self, key, value):
        qry = self.collection.where(key, '==', value)
        strm = await qry.get()
        docs = [v for v in strm]
        return {
            doc.id.split("@")[0]: doc.to_dict()
            for doc in docs
        }

class DocStore:
    def __init__(self, config):

        logger.debug("Opening firestore...")

        if "service-account-key" in config:
            logger.info("Using credentials file")
            self.db = firestore.AsyncClient.from_service_account_json(
                config["service-account-key"],
                project=config["project"],
            )
        else:
            logger.info("Using default creds")
            self.db = firestore.AsyncClient(
                project=config["project"],
            )

        logger.debug("Opened")

    def collection(self, coll):
        return DocCollection(self.db, coll)

    async def get(self, coll, id, tx=None):
        logger.debug("get %s %s" % (coll, id))
        return await self.collection(coll).get(id, tx)

    async def put(self, coll, id, data):
        logger.debug("put %s %s" % (coll, id))
        await self.collection(coll).set(id, data)

    async def delete(self, coll, id):
        logger.debug("delete %s %s" % (coll, id))
        await self.collection(coll).delete(id)

    async def get_all(self, coll, key, value):
        logger.debug("get_all %s" % coll)
        data = await self.collection(coll).all(key, value)
        return data

class BlobStore:
    def __init__(self, config):

        logger.debug("Opening blobstore...")

        if "service-account-key" in config:
            self.db = storage.Client.from_service_account_json(
                config["service-account-key"],
                project=config["project"],
            )
        else:
            self.db = storage.Client(
                project=config["project"]
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
    def __init__(self, config):

        logger.debug("Opening stores...")
        self.docstore = DocStore(config)
        self.blobstore = BlobStore(config)
        logger.debug("Opened")

    def collection(self, id):
        return self.docstore.db.collection(id)
