import sys
import logging

from .api import Api


def main():
    logging.basicConfig(level=logging.DEBUG)

    logging.getLogger("cachecontrol.controller").setLevel(logging.ERROR)
    logging.getLogger("google.auth.transport.requests").setLevel(logging.ERROR)
    logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)

    if len(sys.argv) != 2:
        print("Usage:\n\tam-svc <config>")
        sys.exit(1)

    api = Api(sys.argv[1])
    api.run()


if __name__ == "__main__":
    main()
