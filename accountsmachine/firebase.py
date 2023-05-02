
import logging

import firebase_admin
from firebase_admin import credentials

logger = logging.getLogger("firebase")
logger.setLevel(logging.DEBUG)

class Firebase:
    def __init__(self, config):

        self.project = config["project"]

        logger.debug("Initialise firebase...")

        logger.info("Initialising on project %s", self.project)

        options = {
            "projectId": self.project
        }

        if "service-account-key" in config:

            logger.info("Using service account key")

            # With creds
            self.creds = credentials.Certificate(
                config["service-account-key"]
            )
        
            self.app = firebase_admin.initialize_app(
                self.creds, options=options
            )

        else:

            self.creds = None

            logger.info("Using default credentials")
            self.app = firebase_admin.initialize_app(options=options)

        logger.debug("Initialised")

