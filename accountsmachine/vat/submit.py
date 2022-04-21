
import datetime
from io import StringIO
import asyncio
import uuid
import json
import logging

from firebase_admin import firestore
import gnucash_uk_vat.model as model

from .. ixbrl_process import IxbrlProcess

logger = logging.getLogger("vat.submit")
logger.setLevel(logging.DEBUG)

class VatSubmission:

    def __init__(self, cli, uid, email, user, renderer):
        self.cli = cli
        self.uid = uid
        self.email = email
        self.user = user
        self.renderer = renderer

    async def clear_filing_history(self, id):

        # Clear out any previous filing reports etc.
        try:
            await self.user.filing(id).delete_report()
        except: pass

        try:
            await self.user.filing(id).data().delete()
        except: pass

        try:
            await self.user.filing(id).status().delete()
        except: pass

    async def set_pending(self, id, cfg):

        cfg["state"] = "pending"
        await self.user.filing(id).put(cfg)

    async def background_submit(self, id):

        log_stream = StringIO()
        sthislog = logging.StreamHandler(log_stream)
        thislog = logging.getLoggerClass()("vat")
        thislog.addHandler(sthislog)

        await self.clear_filing_history(id)

        try:

            try:

                logger.debug("Submission of VAT config %s", id)

                cfg = await self.user.filing(id).get()

                await self.set_pending(id, cfg)

                try:
                    company_number = cfg["company"]
                except Exception as e:
                    raise RuntimeError("No company number in configuration")

                obs = await self.cli.get_open_obligations()

                logger.debug("Period due %s", cfg["due"])
                thislog.info("Period due %s", cfg["due"])

                obl = None
                for o in obs:
                    if str(o.due) == cfg["due"]: obl = o

                if obl is None:
                    raise RuntimeError(
                        "VAT due date %s not found in obligations" % cfg["due"]
                    )

                # Process VAT data to HTML report and VAT record
                html = await self.renderer.render(
                    self.user, self.renderer, id, "vat"
                )

                i = IxbrlProcess()
                vat = i.process(html)

                ordtx = {
                    "time": datetime.datetime.now().isoformat(),
                    "type": "filing",
                    "company": company_number,
                    "kind": "vat",
                    "filing": cfg["label"],
                    "id": id,
                    "email": self.email,
                    "uid": self.uid,
                    "valid": True,
                    "order": {
                        "items": [
                            {
                                "kind": "vat",
                                "description": "VAT filing credit",
                                "quantity": -1,
                            }
                        ]
                    }
                }

                tid = str(uuid.uuid4())

                @firestore.transactional
                async def update_order(tx, ordtx):

                    # Fetches current balance
                    v = self.user.credits().vat()
                    v.use_transaction(tx)

                    bal = await v.get()

                    bal = bal["balance"]

                    if bal < 1:
                        return False, "No VAT credits available"

                    bal -= 1

                    ordtx["status"] = "complete"
                    ordtx["complete"] = True

                    await self.user.credits().vat().put({"balance": bal})
                    await self.user.transaction(tid).put(ordtx)

                    return True, "OK"

                tx = self.user.create_transaction()
                ok, msg = await update_order(tx, ordtx)

                if not ok:
                    raise RuntimeError(msg)

                # Billing written

                await self.user.filing(id).put_report(html.encode("utf-8"))
                await self.user.filing(id).data().put(vat)

                rtn = model.Return()
                rtn.periodKey = obl.periodKey
                rtn.finalised = True
                rtn.vatDueSales = vat["VatDueSales"]
                rtn.vatDueAcquisitions = vat["VatDueAcquisitions"]
                rtn.totalVatDue = vat["TotalVatDue"]
                rtn.vatReclaimedCurrPeriod = vat["VatReclaimedCurrPeriod"]
                rtn.netVatDue = vat["NetVatDue"]
                rtn.totalValueSalesExVAT = vat["TotalValueSalesExVAT"]
                rtn.totalValuePurchasesExVAT = vat["TotalValuePurchasesExVAT"]
                rtn.totalValueGoodsSuppliedExVAT = vat["TotalValueGoodsSuppliedExVAT"]
                rtn.totalAcquisitionsExVAT = vat["TotalAcquisitionsExVAT"]

                thislog.info("VAT record:")
                for k, v in rtn.to_dict().items():
                    thislog.info("  %s: %s", k, v)

                thislog.info("Submitting VAT return...")

                await self.cli.submit_vat_return(rtn)
                thislog.info("Success.")

                await self.user.filing(id).status().put({
                    "report": log_stream.getvalue()
                })

            except Exception as e:

                # It all went wrong.
                logger.debug("background_submit: Exception: %s", e)
                thislog.error("background_submit: Exception: %s", e)

                l = log_stream.getvalue()

                # Put the log in a filing status.
                await self.user.filing(id).status().put({
                    "report": l
                })

                # The filed report is empty.
                await self.user.filing(id).put_report("".encode("utf-8"))

                # Here we're reversing the charged credit as a transaction.

                @firestore.transactional
                async def update_order(tx, ordtx):

                    # Get current config
                    cfg = await tx.filing(id).get()

                    # Fetches current balance
                    bal = await tx.balance().get("balance")

                    bal["credits"]["vat"] += 1
                    bal["time"] = datetime.datetime.now().isoformat()

                    ordtx["status"] = "cancelled"
                    ordtx["complete"] = False
                    ordtx["order"] = {
                        "items": [
                            {
                                "kind": "vat",
                                "description": "VAT filing, resulted in error",
                                "quantity": 0,
                            }
                        ]
                    }

                    cfg["state"] = "errored"

                    await tx.balance().put("balance", bal)
                    await tx.transaction().put(tid, ordtx)
                    await self.user.filing(id).put(cfg)

                tx = self.user.create_transaction()
                await update_order(tx, ordtx)

                return

            cfg = await self.user.filing(id).get()
            cfg["state"] = "published"
            await self.user.filing(id).put(cfg)

        except Exception as e:

            logger.debug("background_submit: Exception: %s", e)

            try:
                await self.user.filing(id).status().put({
                    "report": str(e)
                })
            except: pass

    async def submit(self, id):

        rec = await self.user.filing(id).get()

        # Quick credit check before committing to background task
        try:
            balance = await self.user.credits().vat().get()
            balance = balance["balance"]
        except:
            balance = 0

        if balance < 1:
            raise RuntimeError("No VAT credits available")

        asyncio.create_task(
            self.background_submit(id)
        )

