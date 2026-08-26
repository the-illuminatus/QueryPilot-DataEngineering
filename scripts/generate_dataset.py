"""Generates a synthetic, seeded e-commerce dataset -- customers, products,
orders, order_items, payments -- as the raw source-system extract consumed
by the ingestion pipeline. Implements the Phase 2 dataset contract.

Faker is a generation-time-only dependency (see requirements-dev.txt); it
is never imported by the runtime ingestion/validation/transformation code.

The base dataset is generated fully relationally consistent (valid foreign
keys, in-range values, order totals that reconcile with their line items),
then a small, fixed percentage of rows per entity are deliberately
corrupted so the later data-quality stage has real, explainable defects to
catch. Every injected defect corresponds to a documented validation rule
from the Phase 2 design.

All dates are drawn from a fixed reference window, never from the wall
clock, so running this script twice with the same seed on any date
produces byte-identical output.

Usage:
    python scripts/generate_dataset.py
"""

import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

from faker import Faker

SEED = 42

N_CUSTOMERS = 500
N_PRODUCTS = 100
N_ORDERS = 2000
N_ORDER_ITEMS = 5000
N_PAYMENTS = 2200
DEFECT_RATE = 0.04

# Fixed reference dates -- NOT datetime.now() -- so the dataset is
# reproducible regardless of what day the generator is actually run on.
DATASET_AS_OF = date(2026, 8, 1)
SIGNUP_START = date(2023, 1, 1)
FUTURE_DATE = date(2099, 1, 1)

CATEGORIES = [
    "Electronics",
    "Home & Kitchen",
    "Clothing",
    "Books",
    "Sports & Outdoors",
    "Beauty",
    "Toys & Games",
    "Grocery",
    "Automotive",
    "Office Supplies",
]
ORDER_STATUSES = ["PLACED", "SHIPPED", "DELIVERED", "CANCELLED", "RETURNED"]
ORDER_STATUS_WEIGHTS = [15, 20, 45, 12, 8]
PAYMENT_METHODS = ["CREDIT_CARD", "DEBIT_CARD", "UPI", "NET_BANKING", "WALLET", "COD"]
PAYMENT_STATUSES = ["SUCCESS", "FAILED", "PENDING", "REFUNDED"]

CUSTOMER_COLUMNS = ["customer_id", "full_name", "email", "city", "country", "signup_date"]
PRODUCT_COLUMNS = ["product_id", "product_name", "category", "price"]
ORDER_COLUMNS = ["order_id", "customer_id", "order_date", "status", "total_amount"]
ORDER_ITEM_COLUMNS = ["order_item_id", "order_id", "product_id", "quantity", "unit_price"]
PAYMENT_COLUMNS = [
    "payment_id",
    "order_id",
    "payment_date",
    "payment_method",
    "payment_status",
    "amount",
]

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "data" / "raw" / "_incoming"


def random_date(rng: random.Random, start: date, end: date) -> date:
    if end <= start:
        return start
    return start + timedelta(days=rng.randint(0, (end - start).days))


# ---------------------------------------------------------------------------
# Clean, relationally consistent generation
# ---------------------------------------------------------------------------


def generate_customers(fake: Faker, rng: random.Random) -> list:
    rows = []
    for i in range(1, N_CUSTOMERS + 1):
        signup = random_date(rng, SIGNUP_START, DATASET_AS_OF)
        rows.append(
            {
                "customer_id": f"C{i:05d}",
                "full_name": fake.name(),
                "email": fake.unique.email(),
                "city": fake.city(),
                "country": fake.country(),
                "signup_date": signup.isoformat(),
            }
        )
    return rows


def generate_products(fake: Faker, rng: random.Random) -> list:
    rows = []
    for i in range(1, N_PRODUCTS + 1):
        rows.append(
            {
                "product_id": f"P{i:04d}",
                "product_name": fake.unique.catch_phrase(),
                "category": rng.choice(CATEGORIES),
                "price": round(rng.uniform(5, 500), 2),
            }
        )
    return rows


def generate_orders(rng: random.Random, customers: list) -> list:
    rows = []
    for i in range(1, N_ORDERS + 1):
        customer = rng.choice(customers)
        signup = date.fromisoformat(customer["signup_date"])
        order_date = random_date(rng, signup, DATASET_AS_OF)
        rows.append(
            {
                "order_id": f"O{i:06d}",
                "customer_id": customer["customer_id"],
                "order_date": order_date.isoformat(),
                "status": rng.choices(ORDER_STATUSES, weights=ORDER_STATUS_WEIGHTS)[0],
                # Filled in by reconcile_order_totals() once order_items exist.
                "total_amount": 0.0,
            }
        )
    return rows


def generate_order_items(rng: random.Random, orders: list, products: list) -> list:
    rows = []
    for i in range(1, N_ORDER_ITEMS + 1):
        order = rng.choice(orders)
        product = rng.choice(products)
        rows.append(
            {
                "order_item_id": f"OI{i:07d}",
                "order_id": order["order_id"],
                "product_id": product["product_id"],
                "quantity": rng.randint(1, 5),
                # Price at time of order -- intentionally independent of
                # (but close to) the product's current list price.
                "unit_price": round(product["price"] * rng.uniform(0.9, 1.1), 2),
            }
        )
    return rows


def reconcile_order_totals(orders: list, order_items: list) -> None:
    totals = {}
    for item in order_items:
        totals[item["order_id"]] = (
            totals.get(item["order_id"], 0.0) + item["quantity"] * item["unit_price"]
        )
    for order in orders:
        order["total_amount"] = round(totals.get(order["order_id"], 0.0), 2)


def generate_payments(rng: random.Random, orders: list) -> list:
    rows = []
    shuffled = list(orders)
    rng.shuffle(shuffled)
    extra_needed = max(0, N_PAYMENTS - len(orders))
    retry_order_ids = {o["order_id"] for o in shuffled[:extra_needed]}

    payment_seq = 0

    def next_payment_id() -> str:
        nonlocal payment_seq
        payment_seq += 1
        return f"PAY{payment_seq:06d}"

    for order in orders:
        order_date = date.fromisoformat(order["order_date"])
        needs_retry = order["order_id"] in retry_order_ids
        first_date = random_date(rng, order_date, DATASET_AS_OF)
        rows.append(
            {
                "payment_id": next_payment_id(),
                "order_id": order["order_id"],
                "payment_date": first_date.isoformat(),
                "payment_method": rng.choice(PAYMENT_METHODS),
                "payment_status": "FAILED" if needs_retry else "SUCCESS",
                "amount": order["total_amount"],
            }
        )
        if needs_retry:
            retry_date = min(first_date + timedelta(days=rng.randint(0, 2)), DATASET_AS_OF)
            rows.append(
                {
                    "payment_id": next_payment_id(),
                    "order_id": order["order_id"],
                    "payment_date": retry_date.isoformat(),
                    "payment_method": rng.choice(PAYMENT_METHODS),
                    "payment_status": "SUCCESS",
                    "amount": order["total_amount"],
                }
            )
    return rows


# ---------------------------------------------------------------------------
# Deliberate, bounded defect injection -- one defect type per selected row,
# each mapped directly to a documented Phase 2 validation rule.
# ---------------------------------------------------------------------------


def _sample_indices(rows: list, rng: random.Random) -> list:
    n = max(1, int(len(rows) * DEFECT_RATE))
    return rng.sample(range(len(rows)), n)


def _other_row(rows: list, row: dict, rng: random.Random) -> dict:
    return rng.choice([r for r in rows if r is not row])


def inject_customer_defects(rows: list, rng: random.Random) -> dict:
    counts = {}
    defect_types = [
        "missing_full_name",
        "missing_email",
        "invalid_email_format",
        "future_signup_date",
        "duplicate_customer_id",
        "duplicate_email",
    ]
    for idx in _sample_indices(rows, rng):
        row = rows[idx]
        defect = rng.choice(defect_types)
        if defect == "missing_full_name":
            row["full_name"] = ""
        elif defect == "missing_email":
            row["email"] = ""
        elif defect == "invalid_email_format":
            row["email"] = "not-an-email"
        elif defect == "future_signup_date":
            row["signup_date"] = FUTURE_DATE.isoformat()
        elif defect == "duplicate_customer_id":
            row["customer_id"] = _other_row(rows, row, rng)["customer_id"]
        elif defect == "duplicate_email":
            row["email"] = _other_row(rows, row, rng)["email"]
        counts[defect] = counts.get(defect, 0) + 1
    return counts


def inject_product_defects(rows: list, rng: random.Random) -> dict:
    counts = {}
    defect_types = ["missing_product_name", "missing_category", "negative_price", "duplicate_product_id"]
    for idx in _sample_indices(rows, rng):
        row = rows[idx]
        defect = rng.choice(defect_types)
        if defect == "missing_product_name":
            row["product_name"] = ""
        elif defect == "missing_category":
            row["category"] = ""
        elif defect == "negative_price":
            row["price"] = -row["price"] if row["price"] else -9.99
        elif defect == "duplicate_product_id":
            row["product_id"] = _other_row(rows, row, rng)["product_id"]
        counts[defect] = counts.get(defect, 0) + 1
    return counts


def inject_order_defects(rows: list, rng: random.Random) -> dict:
    counts = {}
    defect_types = [
        "missing_order_date",
        "missing_status",
        "invalid_customer_fk",
        "invalid_status_enum",
        "negative_total_amount",
        "future_order_date",
        "malformed_order_date",
        "duplicate_order_id",
    ]
    for idx in _sample_indices(rows, rng):
        row = rows[idx]
        defect = rng.choice(defect_types)
        if defect == "missing_order_date":
            row["order_date"] = ""
        elif defect == "missing_status":
            row["status"] = ""
        elif defect == "invalid_customer_fk":
            row["customer_id"] = "C99999"
        elif defect == "invalid_status_enum":
            row["status"] = "UNKNOWN"
        elif defect == "negative_total_amount":
            row["total_amount"] = -row["total_amount"] if row["total_amount"] else -1.0
        elif defect == "future_order_date":
            row["order_date"] = FUTURE_DATE.isoformat()
        elif defect == "malformed_order_date":
            row["order_date"] = "31-13-2026"
        elif defect == "duplicate_order_id":
            row["order_id"] = _other_row(rows, row, rng)["order_id"]
        counts[defect] = counts.get(defect, 0) + 1
    return counts


def inject_order_item_defects(rows: list, rng: random.Random) -> dict:
    counts = {}
    defect_types = [
        "missing_quantity",
        "invalid_order_fk",
        "invalid_product_fk",
        "zero_quantity",
        "negative_quantity",
        "negative_unit_price",
        "duplicate_order_item_id",
    ]
    for idx in _sample_indices(rows, rng):
        row = rows[idx]
        defect = rng.choice(defect_types)
        if defect == "missing_quantity":
            row["quantity"] = ""
        elif defect == "invalid_order_fk":
            row["order_id"] = "O999999"
        elif defect == "invalid_product_fk":
            row["product_id"] = "P9999"
        elif defect == "zero_quantity":
            row["quantity"] = 0
        elif defect == "negative_quantity":
            row["quantity"] = -row["quantity"] if row["quantity"] else -1
        elif defect == "negative_unit_price":
            row["unit_price"] = -row["unit_price"] if row["unit_price"] else -1.0
        elif defect == "duplicate_order_item_id":
            row["order_item_id"] = _other_row(rows, row, rng)["order_item_id"]
        counts[defect] = counts.get(defect, 0) + 1
    return counts


def inject_payment_defects(rows: list, rng: random.Random) -> dict:
    counts = {}
    defect_types = [
        "missing_payment_date",
        "invalid_order_fk",
        "invalid_payment_method",
        "invalid_payment_status",
        "negative_amount",
        "future_payment_date",
        "malformed_payment_date",
        "duplicate_payment_id",
    ]
    for idx in _sample_indices(rows, rng):
        row = rows[idx]
        defect = rng.choice(defect_types)
        if defect == "missing_payment_date":
            row["payment_date"] = ""
        elif defect == "invalid_order_fk":
            row["order_id"] = "O999999"
        elif defect == "invalid_payment_method":
            row["payment_method"] = "BITCOIN"
        elif defect == "invalid_payment_status":
            row["payment_status"] = "UNKNOWN"
        elif defect == "negative_amount":
            row["amount"] = -row["amount"] if row["amount"] else -1.0
        elif defect == "future_payment_date":
            row["payment_date"] = FUTURE_DATE.isoformat()
        elif defect == "malformed_payment_date":
            row["payment_date"] = "not-a-date"
        elif defect == "duplicate_payment_id":
            row["payment_id"] = _other_row(rows, row, rng)["payment_id"]
        counts[defect] = counts.get(defect, 0) + 1
    return counts


def write_csv(entity: str, columns: list, rows: list) -> Path:
    output_path = OUTPUT_DIR / entity / f"{entity}.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return output_path


def main() -> None:
    rng = random.Random(SEED)
    fake = Faker()
    fake.seed_instance(SEED)

    print(f"Generating synthetic dataset (seed={SEED})...")

    customers = generate_customers(fake, rng)
    products = generate_products(fake, rng)
    orders = generate_orders(rng, customers)
    order_items = generate_order_items(rng, orders, products)
    reconcile_order_totals(orders, order_items)
    payments = generate_payments(rng, orders)

    defect_summary = {
        "customers": inject_customer_defects(customers, rng),
        "products": inject_product_defects(products, rng),
        "orders": inject_order_defects(orders, rng),
        "order_items": inject_order_item_defects(order_items, rng),
        "payments": inject_payment_defects(payments, rng),
    }

    write_csv("customers", CUSTOMER_COLUMNS, customers)
    write_csv("products", PRODUCT_COLUMNS, products)
    write_csv("orders", ORDER_COLUMNS, orders)
    write_csv("order_items", ORDER_ITEM_COLUMNS, order_items)
    write_csv("payments", PAYMENT_COLUMNS, payments)

    print(
        f"Wrote {len(customers)} customers, {len(products)} products, "
        f"{len(orders)} orders, {len(order_items)} order_items, "
        f"{len(payments)} payments to {OUTPUT_DIR}"
    )
    print("Injected defect summary:")
    print(json.dumps(defect_summary, indent=2))


if __name__ == "__main__":
    main()
