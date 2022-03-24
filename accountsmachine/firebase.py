
import logging

import firebase_admin
from firebase_admin import credentials

logger = logging.getLogger("firebase")
logger.setLevel(logging.DEBUG)

class Firebase:
    def __init__(self, config):
        self.project = config["project"]

        logger.debug("Initialise firebase...")

        cred = credentials.Certificate(
            config["svc-account-key"]
        )
        
        firebase_admin.initialize_app(cred)

        logger.debug("Initialised")

