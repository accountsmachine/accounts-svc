
from datetime import datetime, timezone
import math

product = {
    "vat": {
        "description": "VAT return",
#        "permitted": 10,
#        "price": 650,
        "permitted": 4,
        "price": 0,
        "discount": 0.995,
        "min_purchase": 1,
    },
    "corptax": {
        "description": "Corp. tax filing",
        "permitted": 4,
        "price": 1450,
        "discount": 0.995,
        "min_purchase": 1,
    },
    "accounts": {
        "description": "Accounts filing",
        "permitted": 4,
        "price": 950,
        "discount": 0.995,
        "min_purchase": 1,
    }
}

def purchase_price(base, units, discount=0.98):
    return base * units * (discount ** (units - 1))

# Validate order for internal integrity
def verify_order(order, package, vat_rate):

    pkg_discount = None
    if package:
        if package.expiry > datetime.now(timezone.utc):
            if package.discount:
                pkg_discount = package.discount

    subtotal = 0

    for item in order["items"]:

        kind = item["kind"]
        count = item["quantity"]
        amount = item["amount"]
        disc = item["discount"]

        if kind not in product:
            raise InvalidOrder("We don't sell you one of those.")

        resource = product[kind]

        price = math.floor(
            purchase_price(
                resource["price"], count, resource["discount"]
            )
        )

        discount = (resource["price"] * count) - price

        adj = 0
        if pkg_discount:
            if getattr(pkg_discount, kind):
                adj = round(getattr(pkg_discount, kind) * price)
                price -= adj
                discount += adj

        if amount != price:
            raise InvalidOrder("Wrong price")

        if disc != discount:
            raise InvalidOrder("Wrong discount")

        subtotal += amount

    if subtotal != order["subtotal"]:
        raise InvalidOrder("Computed subtotal is wrong")

    # This avoids rounding errors.
    if abs(order["vat_rate"] - vat_rate) > 0.00005:
        raise InvalidOrder("Tax rate is wrong")

    vat = round(subtotal * order["vat_rate"])

    if vat != order["vat"]:
        raise InvalidOrder("VAT calculation is wrong")

    total = subtotal + vat

    if total != order["total"]:
        raise InvalidOrder("Total calculation is wrong")

# Returns potential new balance
def get_order_delta(order):

    deltas = {}

    subtotal = 0

    for item in order["items"]:

        kind = item["kind"]
        count = item["quantity"]
        amount = item["amount"]

        if kind not in deltas:
            deltas[kind] = 0

        deltas[kind] += count

    return deltas
