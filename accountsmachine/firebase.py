
import logging

import firebase_admin
from firebase_admin import credentials

logger = logging.getLogger("firebase")
logger.setLevel(logging.DEBUG)

class Firebase:
    def __init__(self, config):
        self.project = config["project"]

        logger.debug("Initialise firebase...")

        # With creds
#        cred = credentials.Certificate(
#            config["svc-account-key"]
#        )
        
#        firebase_admin.initialize_app(cred)

        firebase_admin.initialize_app()

        logger.debug("Initialised")

