
import math
import pytest
from datetime import datetime, timezone, timedelta
from accountsmachine.commerce.order import (
    purchase_price, verify_order, get_order_delta, product,
)
from accountsmachine.commerce.exceptions import InvalidOrder
from accountsmachine.admin.referral import Package, Referrer, JoinUpCredits, Discount


def make_package(discount=None, expired=False):
    if expired:
        expiry = datetime.now(timezone.utc) - timedelta(days=1)
    else:
        expiry = datetime.now(timezone.utc) + timedelta(days=30)
    referrer = Referrer(name="Test", id="test-ref")
    return Package(
        id="TEST",
        referrer=referrer,
        expiry=expiry,
        join_up_credits=JoinUpCredits(),
        discount=discount or Discount(),
    )


class TestPurchasePrice:

    def test_single_unit(self):
        assert purchase_price(1000, 1) == 1000

    def test_multiple_units_applies_discount(self):
        result = purchase_price(1000, 3)
        expected = 1000 * 3 * (0.98 ** 2)
        assert result == pytest.approx(expected)

    def test_custom_discount(self):
        result = purchase_price(1000, 2, discount=0.5)
        expected = 1000 * 2 * (0.5 ** 1)
        assert result == pytest.approx(expected)

    def test_zero_price(self):
        assert purchase_price(0, 5) == 0


class TestGetOrderDelta:

    def test_single_item(self):
        order = {
            "items": [
                {"kind": "vat", "quantity": 3, "amount": 0},
            ]
        }
        assert get_order_delta(order) == {"vat": 3}

    def test_multiple_items(self):
        order = {
            "items": [
                {"kind": "vat", "quantity": 2, "amount": 0},
                {"kind": "corptax", "quantity": 1, "amount": 0},
            ]
        }
        deltas = get_order_delta(order)
        assert deltas == {"vat": 2, "corptax": 1}

    def test_same_kind_accumulates(self):
        order = {
            "items": [
                {"kind": "vat", "quantity": 2, "amount": 0},
                {"kind": "vat", "quantity": 3, "amount": 0},
            ]
        }
        assert get_order_delta(order) == {"vat": 5}

    def test_empty_order(self):
        assert get_order_delta({"items": []}) == {}


class TestVerifyOrder:

    def _build_order(self, items, vat_rate=0.2):
        subtotal = sum(i["amount"] for i in items)
        vat = round(subtotal * vat_rate)
        return {
            "items": items,
            "subtotal": subtotal,
            "vat_rate": vat_rate,
            "vat": vat,
            "total": subtotal + vat,
        }

    def _make_item(self, kind, quantity):
        resource = product[kind]
        price = math.floor(
            purchase_price(
                resource["price"], quantity, resource["discount"]
            )
        )
        discount = (resource["price"] * quantity) - price
        return {
            "kind": kind,
            "quantity": quantity,
            "amount": price,
            "discount": discount,
        }

    def test_valid_order_passes(self):
        item = self._make_item("corptax", 2)
        order = self._build_order([item])
        pkg = make_package()
        verify_order(order, pkg, 0.2)

    def test_wrong_price_raises(self):
        item = self._make_item("corptax", 1)
        item["amount"] = 9999
        order = self._build_order([item])
        pkg = make_package()
        with pytest.raises(InvalidOrder, match="Wrong price"):
            verify_order(order, pkg, 0.2)

    def test_wrong_subtotal_raises(self):
        item = self._make_item("corptax", 1)
        order = self._build_order([item])
        order["subtotal"] = 0
        pkg = make_package()
        with pytest.raises(InvalidOrder, match="subtotal"):
            verify_order(order, pkg, 0.2)

    def test_wrong_vat_rate_raises(self):
        item = self._make_item("corptax", 1)
        order = self._build_order([item], vat_rate=0.2)
        pkg = make_package()
        with pytest.raises(InvalidOrder, match="Tax rate"):
            verify_order(order, pkg, 0.25)

    def test_wrong_total_raises(self):
        item = self._make_item("corptax", 1)
        order = self._build_order([item])
        order["total"] = 0
        pkg = make_package()
        with pytest.raises(InvalidOrder, match="Total"):
            verify_order(order, pkg, 0.2)

    def test_unknown_product_raises(self):
        item = {
            "kind": "unicorn",
            "quantity": 1,
            "amount": 100,
            "discount": 0,
        }
        order = self._build_order([item])
        pkg = make_package()
        with pytest.raises(InvalidOrder):
            verify_order(order, pkg, 0.2)

    def test_expired_package_ignores_discount(self):
        disc = Discount(vat=0.5, corptax=0.5, accounts=0.5)
        pkg = make_package(discount=disc, expired=True)
        item = self._make_item("corptax", 1)
        order = self._build_order([item])
        verify_order(order, pkg, 0.2)

    def test_free_product_valid(self):
        item = self._make_item("vat", 1)
        order = self._build_order([item])
        pkg = make_package()
        verify_order(order, pkg, 0.2)
