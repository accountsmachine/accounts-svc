
product = {
    "vat": {
        "description": "VAT return",
        "permitted": 10,
        "price": 650,
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

