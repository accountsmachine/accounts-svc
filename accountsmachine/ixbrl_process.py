
from lxml import etree as ET
import logging

import ixbrl_parse.ixbrl as ix

logger = logging.getLogger("vat")
logger.setLevel(logging.DEBUG)

class IxbrlProcess:

    def get_tree(self, data):
        return ET.fromstring(data.encode("utf-8"))

    def cdump(self, ctxt):
        values = []
        for name, value in ctxt.values.items():
#            name = name.localname
            value = value.to_value().get_value()
            if isinstance(value, float):
                values.append((name, value))
            else:
                values.append((name, str(value)))
        for rel, c in ctxt.children.items():
            values.extend(self.cdump(c))
        return values

    def process(self, data):

        tree = self.get_tree(data)
        i = ix.parse(tree)

        vals = self.cdump(i.root)

        ret = {}
        
        for k, v in vals:
            k = k.localname
            ret[k] = v

        return ret

    def process_with_schema(self, data):

        tree = self.get_tree(data)
        i = ix.parse(tree)

        try:
            schema = i.load_schema(None)
        except:
            schema = None

        vals = self.cdump(i.root)

        ret = {}
        
        for k, v in vals:
            try:
                if schema:
                    k = schema.get_label(k)
                else:
                    k = k.localname
            except Exception as e:
                k = k.localname

            ret[k] = v

        return ret
