
import json
import base64
import glob
import sys
import base64
import logging
import asyncio

#from google.cloud import firestore
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
    def all(self):
        return {
            doc.id: doc.to_dict()
            for doc in self.collection.stream()
        }

class Store:
    def __init__(self, config, firebase):

        logger.debug("Opening firestore...")
        self.db = firestore.client()
        logger.debug("Opened")

    def collection(self, coll):
        return Collection(self.db, coll)

    def key(self, coll, id):
        return "%s#%s" % (coll, id)

    async def get(self, coll, id):
        logger.debug("get %s %s" % (coll, id))
        return self.collection(coll)[id]

    async def put(self, coll, id, data):
        logger.debug("put %s %s" % (coll, id))
        self.collection(coll)[id] = data

    async def delete(self, coll, id):
        logger.debug("delete %s %s" % (coll, id))
        del self.collection(coll)[id]

    async def get_blob(self, coll, id):
        logger.debug("getblob %s %s" % (coll, id))
        return self.collection(coll)[id]["blob"]

    async def put_blob(self, coll, id, data):
        logger.debug("putblob %s %s" % (coll, id))
        self.collection(coll)[id] = { "blob": data }

    async def get_all(self, coll):
        logger.debug("get_all %s" % coll)
        return self.collection(coll).all()

