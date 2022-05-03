
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

class Referrer:
    def __init__(self, name, id):
        self.name = name
        self.id = id
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
        }

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
            datetime.datetime.utcnow() + datetime.timedelta(days=self.expiry)
        )

        return AllocatedPackage(self.id, self.referrer, expiry,
                                self.join_up_credits, self.discount)

class AllocatedPackage:

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
            "expiry": self.expiry.isoformat(),
            "referrer": self.referrer.to_dict(),
            "join-up-credits": self.join_up_credits.to_dict(),
            "discount": self.discount.to_dict(),
        }

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

            )

        }

#        pkg = self.get_package("LAUNCHPAD")
#        print(json.dumps(pkg.to_dict()))

#        all = pkg.allocate()
#        print(json.dumps(all.to_dict()))
        

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
#        return Offer(id="STANDARD")
        return self.get_package("LAUNCHPAD")

