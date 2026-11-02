
import pytest
from datetime import datetime, timezone, timedelta
from accountsmachine.admin.referral import (
    JoinUpCredits, Discount, Referrer, Offer, Package, Referrals,
)


class TestJoinUpCredits:

    def test_defaults(self):
        c = JoinUpCredits()
        assert c.vat == 0
        assert c.corptax == 0
        assert c.accounts == 0

    def test_to_dict(self):
        c = JoinUpCredits(vat=5, corptax=2, accounts=1)
        assert c.to_dict() == {"vat": 5, "corptax": 2, "accounts": 1}

    def test_roundtrip(self):
        c = JoinUpCredits(vat=5, corptax=2, accounts=1)
        c2 = JoinUpCredits.from_dict(c.to_dict())
        assert c2.vat == 5
        assert c2.corptax == 2
        assert c2.accounts == 1


class TestDiscount:

    def test_defaults(self):
        d = Discount()
        assert d.vat == 0
        assert d.corptax == 0
        assert d.accounts == 0

    def test_roundtrip(self):
        d = Discount(vat=0.2, corptax=0.1, accounts=0.15)
        d2 = Discount.from_dict(d.to_dict())
        assert d2.vat == 0.2
        assert d2.corptax == 0.1
        assert d2.accounts == 0.15


class TestReferrer:

    def test_roundtrip(self):
        r = Referrer(name="Test Partner", id="abc-123")
        r2 = Referrer.from_dict(r.to_dict())
        assert r2.name == "Test Partner"
        assert r2.id == "abc-123"


class TestPackage:

    def test_roundtrip(self):
        expiry = datetime.now(timezone.utc) + timedelta(days=30)
        p = Package(
            id="TEST",
            referrer=Referrer(name="Test", id="ref-1"),
            expiry=expiry,
            join_up_credits=JoinUpCredits(vat=3, corptax=1, accounts=1),
            discount=Discount(vat=0.2, corptax=0.1, accounts=0),
        )
        d = p.to_dict()
        p2 = Package.from_dict(d)
        assert p2.id == "TEST"
        assert p2.join_up_credits.vat == 3
        assert p2.discount.corptax == 0.1
        assert p2.referrer.name == "Test"


class TestReferrals:

    def test_known_referral(self):
        r = Referrals()
        pkg = r.get_package("LAUNCHPAD")
        assert pkg is not None
        assert pkg.id == "LAUNCHPAD"
        assert pkg.join_up_credits.vat == 6

    def test_unknown_referral(self):
        r = Referrals()
        assert r.get_package("NONEXISTENT") is None

    def test_default_package(self):
        r = Referrals()
        pkg = r.default_package()
        assert pkg is not None
        assert pkg.id == "STANDARD"

    def test_allocated_package_has_future_expiry(self):
        r = Referrals()
        pkg = r.get_package("LAUNCHPAD")
        assert pkg.expiry > datetime.now(timezone.utc)
