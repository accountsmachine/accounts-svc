
from datetime import datetime, timezone, timedelta
import logging
import json

logger = logging.getLogger("admin.referral")
logger.setLevel(logging.INFO)

class JoinUpCredits:
    def __init__(self, vat=0, corptax=0, accounts=0):
        self.vat = vat
        self.corptax = corptax
        self.accounts = accounts
    def to_dict(self):
        return {
            "vat": self.vat,
            "corptax": self.corptax,
            "accounts": self.accounts,
        }

    @staticmethod
    def from_dict(d):
        return JoinUpCredits(
            vat=d["vat"],
            corptax=d["corptax"],
            accounts=d["accounts"],
        )

class Discount:
    def __init__(self, vat=0, corptax=0, accounts=0):
        self.vat = vat
        self.corptax = corptax
        self.accounts = accounts
    def to_dict(self):
        return {
            "vat": self.vat,
            "corptax": self.corptax,
            "accounts": self.accounts,
        }

    @staticmethod
    def from_dict(d):
        return Discount(
            vat=d["vat"],
            corptax=d["corptax"],
            accounts=d["accounts"],
        )

class Referrer:
    def __init__(self, name, id):
        self.name = name
        self.id = id
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
        }

    @staticmethod
    def from_dict(d):
        return Referrer(
            id=d["id"],
            name=d["name"],
        )

class Offer:

    def __init__(self, id, referrer, join_up_credits = None, discount = None,
                 expiry_days=0):
        self.id = id
        self.referrer = referrer

        if join_up_credits == None:
            self.join_up_credits = JoinUpCredits()
        else:
            self.join_up_credits = join_up_credits

        if discount == None:
            self.discount = discount()
        else:
            self.discount = discount

        self.expiry = expiry_days

    def to_dict(self):
        return {
            "id": self.id,
            "expiry": self.expiry,
            "referrer": self.referrer.to_dict(),
            "join-up-credits": self.join_up_credits.to_dict(),
            "discount": self.discount.to_dict(),
        }

    # Take a package and allocate it, which basically just puts an expiry
    # date based on current time
    def allocate(self):
        
        expiry = (
            datetime.now(timezone.utc) + timedelta(days=self.expiry)
        )

        return Package(self.id, self.referrer, expiry,
                                self.join_up_credits, self.discount)

class Package:

    def __init__(self, id, referrer, expiry, join_up_credits = None,
                 discount = None):

        self.id = id
        self.expiry = expiry
        self.referrer = referrer

        if join_up_credits == None:
            self.join_up_credits = JoinUpCredits()
        else:
            self.join_up_credits = join_up_credits

        if discount == None:
            self.discount = discount()
        else:
            self.discount = discount

        self.expiry = expiry

    def to_dict(self):
        return {
            "id": self.id,
            "expiry": self.expiry,
            "referrer": self.referrer.to_dict(),
            "join-up-credits": self.join_up_credits.to_dict(),
            "discount": self.discount.to_dict(),
        }

    @staticmethod
    def from_dict(d):
        return Package(
            id=d["id"],
            referrer=Referrer.from_dict(d["referrer"]),
            expiry=d["expiry"],
            join_up_credits=JoinUpCredits.from_dict(d["join-up-credits"]),
            discount=Discount.from_dict(d["discount"])
        )

class Referrals:

    def __init__(self):

        self.referrals = {

            'LAUNCHPAD': Offer(

                id="LAUNCHPAD",

                join_up_credits = JoinUpCredits(
                    vat=6, corptax=1, accounts=1,
                ),

                discount = Discount(
                    vat=0.2, corptax=0.2, accounts=0.2,
                ),

                referrer = Referrer(
                    name='Accounts Machine beta',
                    id='20d07be0-1da0-41e8-ac15-6e950cec36c3'
                ),

                expiry_days=712,

            ),

            'STANDARD': Offer(

                id="STANDARD",

                join_up_credits = JoinUpCredits(),
                discount = Discount(),

                referrer = Referrer(
                    name='Standard package',
                    id='7b6ef04a-03ee-41c2-89a2-df16c1221b2e'
                ),

                expiry_days=712,

            )

        }

    def get_offer(self, ref):

        if ref in self.referrals:
            return self.referrals[ref]

        return None

    def get_package(self, ref):

        offer = self.get_offer(ref)

        if offer:
            return offer.allocate()

        return None

    def default_package(self):
        return self.get_package("STANDARD")

