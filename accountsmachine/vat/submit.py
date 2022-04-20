
import datetime
from io import StringIO
import asyncio
import uuid
import json
import logging

from firebase_admin import firestore
import gnucash_uk_vat.model as model

from .. ixbrl_process import IxbrlProcess
from . hmrc import Hmrc

logger = logging.getLogger("vat.submit")
logger.setLevel(logging.DEBUG)

class VatSubmission:

    def __init__(self, user, email, config, state, renderer):
        self.user = user
        self.email = email
        self.config = config
        self.state = state
        self.renderer = renderer

    async def clear_filing_history(self, id):

        # Clear out any previous filing reports etc.
        try:
            await state.filing_report().delete(id)
        except: pass

        try:
            await state.filing_data().delete(id)
        except: pass

        try:
            await state.filing_status().delete(id)
        except: pass

    async def set_pending(self, id, cfg):

        cfg["state"] = "pending"
        await state.filing_config().put(id, cfg)

    async def background_submit(self, id):

        state = self.state

        log_stream = StringIO()
        sthislog = logging.StreamHandler(log_stream)
        thislog = logging.getLoggerClass()("vat")
        thislog.addHandler(sthislog)

        self.clear_filing_history(id)

        try:

            try:

                logger.debug("Submission of VAT config %s", id)

                cfg = await state.filing_config().get(id)

                self.set_pending(id, cfg)

                try:
                    company_number = cfg["company"]
                except Exception as e:
                    raise RuntimeError("No company number in configuration")

                cli = Hmrc(self.config, state, company_number)
                obs = await cli.get_open_obligations()

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
                    state, self.renderer, id, "vat"
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
                    "uid": self.user,
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
                async def update_order(stx, tx, ordtx):

                    # Fetches current balance
                    bal = await tx.balance().get("balance")

                    if bal["credits"]["vat"] < 1:
                        return False, "No VAT credits available"

                    bal["credits"]["vat"] -= 1
                    bal["time"] = datetime.datetime.now().isoformat()

                    ordtx["status"] = "complete"
                    ordtx["complete"] = True

                    await tx.balance().put("balance", bal)
                    await tx.transaction().put(tid, ordtx)

                    return True, "OK"

                tx = state.create_transaction()
                ok, msg = await update_order(tx.tx, tx, ordtx)

                if not ok:
                    raise RuntimeError(msg)

                # Billing written

                await state.filing_report().put(id, html.encode("utf-8"))
                await state.filing_data().put(id, vat)

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
                await cli.submit_vat_return(rtn)
                thislog.info("Success.")

                await state.filing_status().put(id, {
                    "report": log_stream.getvalue()
                })

            except Exception as e:

                # It all went wrong.
                logger.debug("background_submit: Exception: %s", e)
                thislog.error("background_submit: Exception: %s", e)

                l = log_stream.getvalue()

                # Put the log in a filing status.
                await state.filing_status().put(id, {
                    "report": l
                })

                # The filed report is empty.
                await state.filing_report().put(id, "".encode("utf-8"))

                # Here we're reversing the charged credit as a transaction.

                @firestore.transactional
                async def update_order(stx, tx, ordtx):

                    # Get current config
                    cfg = await tx.filing_config().get(id)

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
                    await state.filing_config().put(id, cfg)

                tx = state.create_transaction()
                await update_order(tx.tx, tx, ordtx)

                return

            cfg = await state.filing_config().get(id)
            cfg["state"] = "published"
            await state.filing_config().put(id, cfg)

        except Exception as e:

            logger.debug("background_submit: Exception: %s", e)

            try:
                await state.filing_status().put(id, {
                    "report": str(e)
                })
            except: pass

    async def submit(self, id):

        rec = self.state.filing_config().get(id)

        # Quick credit check before committing to background task
        balance = await self.state.balance().get("balance")

        if balance["credits"]["vat"] < 1:
                raise RuntimeError("No VAT credits available")

        asyncio.create_task(
                self.background_submit(id)
        )

