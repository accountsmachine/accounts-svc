
import datetime
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

class Discount:
    def __init__(self, vat=0, corptax=0, accounts=0, expiry_days=0):
        self.vat = vat
        self.corptax = corptax
        self.accounts = accounts
        self.expiry = expiry_days
    def to_dict(self):
        return {
            "vat": self.vat,
            "corptax": self.corptax,
            "accounts": self.accounts,
            "expiry": self.expiry
        }

class Referrer:
    def __init__(self, name, id):
        self.name = name
        self.id = id
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
        }

class Package:

    def __init__(self, id, referrer, join_up_credits = None, discount = None):

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

    def to_dict(self):
        return {
            "id": self.id,
            "referrer": self.referrer.to_dict(),
            "join-up-credits": self.join_up_credits.to_dict(),
            "discount": self.discount.to_dict(),
        }

class Referrals:

    def __init__(self):

        self.referrals = {

            'LAUNCHPAD': Package(

                id="LAUNCHPAD",

                join_up_credits = JoinUpCredits(
                    vat=6, corptax=1, accounts=1,
                ),

                discount = Discount(
                    vat=0.2, corptax=0.2, accounts=0.2,
                    expiry_days=712,
                ),

                referrer = Referrer(
                    name='Accounts Machine beta',
                    id='20d07be0-1da0-41e8-ac15-6e950cec36c3'
                )

            )

        }

    def get_package(self, ref):

        if ref in self.referrals: return self.referrals[ref]

        return None

    def default_package(self):
#        return Package(id="STANDARD")
        return self.get_package("LAUNCHPAD")

