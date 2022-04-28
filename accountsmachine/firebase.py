
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

        logger.info("Initialising on project %s", self.project)

        options = {
            "projectId": self.project
        }

        firebase_admin.initialize_app(options=options)

        logger.debug("Initialised")

