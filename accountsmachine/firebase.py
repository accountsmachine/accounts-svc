
import logging

import firebase_admin

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

        firebase_admin.initialize_app(options=options)

        logger.debug("Initialised")

