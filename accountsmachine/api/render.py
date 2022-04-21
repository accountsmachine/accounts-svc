
from aiohttp import web
import _jsonnet as j
import os.path
import os
import json
import io
import uuid
import base64
import datetime
import logging

from ixbrl_reporter.config import Config
from ixbrl_reporter.accounts import get_class
from ixbrl_reporter.data_source import DataSource
from ixbrl_reporter.taxonomy import Taxonomy

from .. ixbrl_process import IxbrlProcess
from .. state.books import Books

logger = logging.getLogger("api.render")
logger.setLevel(logging.INFO)

class RendererApi:

    def __init__(self, config):
        self.white_pixel_png = bytes([
            137, 80, 78, 71, 13, 10, 26, 10, 0, 0, 0, 13, 73, 72, 68, 82, 0,
            0, 0, 1, 0, 0, 0, 1, 8, 6, 0, 0, 0, 31, 21, 196, 137, 0, 0, 0, 13,
            73, 68, 65, 84, 8, 153, 99, 248, 255, 255, 255, 127, 0, 9, 251, 3,
            253, 8, 209, 232, 30, 0, 0, 0, 0, 73, 69, 78, 68, 174, 66, 96, 130
        ])
        self.jsonnet_base = config["jsonnet-base"]
        self.base = config["config-base"]
        self.config = ""

    def load(self, dir, filename):

        logger.debug("Request jsonnet: %s %s", dir, filename)

        if filename == "svr-config.jsonnet":
            logger.debug("Handled internally")
            return filename, self.config

        try:
            if dir:
                path = os.path.join(".", dir, filename)
            else:
                path = os.path.join(self.jsonnet_base, filename)

            logger.debug("Try: %s", path)
            with open(path) as f:
                logger.debug("Loaded: %s", path)
                return str(path), f.read()

        except:
            path = os.path.join(self.jsonnet_base, filename)
            with open(path) as f:
                logger.debug("Loaded: %s", path)
                return str(path), f.read()

    def process_jsonnet(self, kind, config):

        self.config = config

        open("svr-config.jsonnet", "w").write(config)

        if ".." in kind:
            raise RuntimeError("Bad kind")
            
        svr = open("%s/base-%s.jsonnet" % (self.base, kind)).read()
        res = j.evaluate_snippet("config", svr, import_callback=self.load)
        return json.loads(res)

    async def logo(self, user, cid):

        try:
            try:
                info = await user.company(cid).logo().get()
                img = await user.company(cid).logo().get_image()
                ct = info["content-type"]
            except:
                img = self.white_pixel_png
                ct = "image/png"

            img = base64.b64encode(img).decode("utf-8")
            img = "data:" + ct + ";base64," + img

            return img

        except Exception as e:
            logger.debug(e)
            raise RuntimeError("Could not load company logo.")


    async def signature(self, user, fid):

        try:
            try:
                info = await user.filing(fid).signature().get()
                img = await user.filing(fid).signature().get_image()
                ct = info["content-type"]
            except:
                img = self.white_pixel_png
                ct = "image/png"

            img = base64.b64encode(img).decode("utf-8")
            img = "data:" + ct + ";base64," + img

            return img

        except Exception as e:
            logger.debug(e)
            raise RuntimeError("Could not load signature.")
        
    def process_to_html(self, obj):

        accounts = None

        try:

            acfg = Config(obj)
            acfg.set("internal.software-name", "accountsmachine.io")
            acfg.set("internal.software-version", "0.0.1")

            kind = acfg.get("accounts.kind")
            file = acfg.get("accounts.file")
            cls = get_class(kind)
            accounts = cls(file)

            ds = DataSource(acfg, accounts)
            elt = ds.get_element("report")

            tx_cfg = acfg.get("report.taxonomy")
            tx = Taxonomy(tx_cfg, ds)

            buf = io.StringIO()

            # FIXME: Giving away free stuff?
#            elt.to_html(tx, buf)
            elt.to_ixbrl(tx, buf)

            return buf.getvalue()

        except Exception as e:
            logger.info("Exception: (%s) %s", type(e), e)
            return "Exception:" + str(e)

    def render_accounts_html(self, kind, config):

        obj = self.process_jsonnet(kind, config)
        return self.process_to_html(obj)

    async def render(self, user, renderer, id, kind):

        try:

            cfg = await user.filing(id).get()

            try:
                cid = cfg["company"]
            except Exception as e:
                raise RuntimeError("No company number in configuration")

            cmp = await user.company(cid).get()

            cfg = {
                "report": cfg,
                "metadata": cmp,
            }

            books = Books(user, cid)
        
            tmp_file = "tmp." + str(uuid.uuid4()) + ".dat"

            mappings = await books.get_mapping()
            logo = await self.logo(user, cid)
            sig = await self.signature(user, id)

            today = datetime.datetime.now().date().isoformat()

            with await books.create_temp_file(tmp_file) as f:
                cfg["report"]["structure"]["accounts_file"] = tmp_file
                cfg["report"]["structure"]["accounts_kind"] = "piecash"
                cfg["report"]["logo"] = logo
                cfg["report"]["signature"] = sig
                cfg["report"]["today"] = today
                cfg["report"]["mappings"] = mappings

                data = json.dumps(cfg)

                html = renderer.render_accounts_html(kind, data)

            return html

        except Exception as e:

            try:
                os.remove(accts_file)
            except: pass

            raise e

    async def to_html(self, request):

        request["auth"].verify_scope("render")
        user = request["state"]

        try:

            id = request.match_info['id']

            cfg = await user.filing(id).get()

            html = await self.render(user, self, id, cfg["kind"])

            return web.Response(text=html, content_type="text/html")

        except Exception as e:

            logger.error("render: Exception: (%s) %s", type(e), e)
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )
        
