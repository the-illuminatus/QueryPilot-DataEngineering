"""Generates a synthetic, seeded India-focused digital-commerce dataset --
customers, products, orders, order_items, payments -- as the raw
source-system extract consumed by the ingestion pipeline. Implements the
Phase 2 dataset contract, localized for an Indian payments/e-commerce
analytics warehouse (see README.md).

This is SYNTHETIC data: realistic Indian names, cities, states, product
catalogue, INR pricing, UPI-heavy payment mix and recent order dates,
generated locally so anyone cloning the repo can reproduce it exactly.
It is not, and is never described as, live or real-time data.

Fully deterministic: the only source of randomness is a single
`random.Random(SEED)`, and every date is drawn from a fixed reference
window, never the wall clock. Running this script twice with the same
seed on any machine on any day produces byte-identical output, so the
dataset stays reproducible without committing large files to Git.

The base dataset is generated fully relationally consistent (valid
foreign keys, in-range INR values, order totals that reconcile with
their line items), then a small, fixed percentage of rows per entity are
deliberately corrupted so the later data-quality stage has real,
explainable defects to catch. Every injected defect corresponds to a
documented validation rule from the Phase 2/3 design.

Usage:
    python scripts/generate_dataset.py
"""

import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 42

N_CUSTOMERS = 500
N_PRODUCTS = 100
N_ORDERS = 2000
N_ORDER_ITEMS = 5000
N_PAYMENTS = 2200
DEFECT_RATE = 0.04

# Fixed reference dates -- NOT datetime.now() -- so the dataset is
# reproducible regardless of what day the generator is actually run on.
# DATASET_AS_OF is deliberately kept close to "now" so the warehouse
# reads as an operational store with recent activity, while still being
# a hard-coded constant rather than the wall clock.
DATASET_AS_OF = date(2026, 8, 25)
SIGNUP_START = date(2023, 1, 1)
FUTURE_DATE = date(2099, 1, 1)

# Real Indian cities paired with their actual state/UT. The weight is a
# rough proxy for e-commerce order density, so metros dominate the
# customer base the way they do in reality.
CITY_STATE_WEIGHTS = [
    ("Mumbai", "Maharashtra", 12),
    ("Pune", "Maharashtra", 8),
    ("Nagpur", "Maharashtra", 3),
    ("Nashik", "Maharashtra", 2),
    ("Bengaluru", "Karnataka", 11),
    ("Mysuru", "Karnataka", 2),
    ("Hyderabad", "Telangana", 9),
    ("Delhi", "Delhi", 11),
    ("Gurugram", "Haryana", 5),
    ("Faridabad", "Haryana", 2),
    ("Noida", "Uttar Pradesh", 5),
    ("Lucknow", "Uttar Pradesh", 3),
    ("Kanpur", "Uttar Pradesh", 2),
    ("Chennai", "Tamil Nadu", 8),
    ("Coimbatore", "Tamil Nadu", 2),
    ("Madurai", "Tamil Nadu", 1),
    ("Ahmedabad", "Gujarat", 6),
    ("Surat", "Gujarat", 3),
    ("Vadodara", "Gujarat", 2),
    ("Rajkot", "Gujarat", 1),
    ("Kolkata", "West Bengal", 7),
    ("Howrah", "West Bengal", 2),
    ("Jaipur", "Rajasthan", 4),
    ("Jodhpur", "Rajasthan", 1),
    ("Udaipur", "Rajasthan", 1),
    ("Indore", "Madhya Pradesh", 3),
    ("Bhopal", "Madhya Pradesh", 2),
    ("Patna", "Bihar", 3),
    ("Bhubaneswar", "Odisha", 2),
    ("Kochi", "Kerala", 3),
    ("Thiruvananthapuram", "Kerala", 2),
    ("Chandigarh", "Chandigarh", 2),
    ("Guwahati", "Assam", 2),
    ("Dehradun", "Uttarakhand", 1),
    ("Raipur", "Chhattisgarh", 1),
    ("Ranchi", "Jharkhand", 1),
    ("Visakhapatnam", "Andhra Pradesh", 3),
    ("Vijayawada", "Andhra Pradesh", 1),
    ("Amritsar", "Punjab", 2),
    ("Ludhiana", "Punjab", 2),
]

FIRST_NAMES = [
    "Aarav", "Aditya", "Arjun", "Vivaan", "Vihaan", "Reyansh", "Ishaan", "Kabir",
    "Rohan", "Rahul", "Rohit", "Amit", "Ankit", "Karan", "Nikhil", "Siddharth",
    "Aryan", "Dev", "Manish", "Suresh", "Rajesh", "Ramesh", "Vikram", "Sanjay",
    "Anil", "Deepak", "Pankaj", "Gaurav", "Harsh", "Yash", "Varun", "Abhishek",
    "Akash", "Naveen", "Prashant", "Sachin", "Vishal", "Krishna", "Sai", "Aman",
    "Aanya", "Aadhya", "Ananya", "Diya", "Isha", "Kavya", "Priya", "Neha",
    "Pooja", "Riya", "Sneha", "Shreya", "Aishwarya", "Divya", "Meera", "Nisha",
    "Anjali", "Swati", "Kritika", "Sakshi", "Tanvi", "Ritu", "Sunita", "Kavita",
    "Rekha", "Deepika", "Aarti", "Payal", "Simran", "Nandini", "Lakshmi", "Radha",
]

LAST_NAMES = [
    "Sharma", "Verma", "Gupta", "Agarwal", "Jain", "Bansal", "Mittal", "Singh",
    "Yadav", "Chauhan", "Rathore", "Patel", "Shah", "Desai", "Mehta", "Modi",
    "Reddy", "Rao", "Naidu", "Nair", "Menon", "Iyer", "Pillai", "Kumar",
    "Das", "Dutta", "Bose", "Banerjee", "Chatterjee", "Mukherjee", "Ghosh", "Sen",
    "Kulkarni", "Deshpande", "Joshi", "Patil", "Gaikwad", "Shetty", "Hegde", "Pai",
    "Khanna", "Kapoor", "Malhotra", "Chopra", "Bhat", "Saxena", "Trivedi", "Pandey",
    "Mishra", "Bhardwaj",
]

EMAIL_DOMAINS = [
    "gmail.com", "gmail.com", "gmail.com", "yahoo.in", "yahoo.com",
    "outlook.com", "hotmail.com", "rediffmail.com",
]

# Relative popularity of each category in the product catalogue and in
# baskets -- everyday low-value categories dominate, big-ticket ones are
# rare, so the order-value distribution looks like real consumer
# e-commerce (lots of small orders, a long tail of expensive ones).
CATEGORY_WEIGHTS = {
    "Grocery & Gourmet": 22,
    "Fashion": 20,
    "Beauty & Personal Care": 16,
    "Home & Kitchen": 12,
    "Books": 10,
    "Toys & Baby": 8,
    "Sports & Fitness": 6,
    "Mobile Accessories": 4,
    "Electronics": 3,
    "Smartphones": 2,
    "Large Appliances": 1,
}

# Per-category INR price band (low, high, step) and a small brand/item
# vocabulary. Prices are drawn on the step so they read like real MRPs
# (e.g. 15990, not 15987.34), and skewed towards the low end of each
# band (see _skewed_price) so a category's typical item is cheap even
# when its ceiling is high.
CATEGORY_CONFIG = {
    "Smartphones": {
        # Budget handsets to flagships -- the wide ceiling is only ever
        # reached by a phone, never by an accessory (accessories are their
        # own category below).
        "band": (6499, 154900, 100),
        "brands": ["Samsung", "Xiaomi", "Redmi", "realme", "OnePlus", "vivo", "OPPO",
                   "Apple", "Motorola", "Nothing", "iQOO"],
        # No storage/spec in the name -- price is drawn across the whole
        # band, so a name must not imply a tier the price then contradicts.
        "items": ["5G Smartphone", "Smartphone"],
    },
    "Mobile Accessories": {
        "band": (149, 4999, 50),
        "brands": ["boAt", "Noise", "Boult", "Portronics", "Ambrane", "pTron",
                   "Spigen", "Stuffcool", "Zebronics", "Mi"],
        "items": ["Wireless Earbuds", "Bluetooth Neckband", "20000mAh Power Bank",
                  "33W Fast Charger", "Tempered Glass", "Silicone Back Cover",
                  "USB-C Cable", "Car Phone Charger"],
    },
    "Electronics": {
        "band": (499, 89990, 100),
        "brands": ["Sony", "LG", "boAt", "JBL", "Noise", "Boult", "Portronics",
                   "HP", "Dell", "Lenovo", "Acer", "Canon"],
        "items": ["Bluetooth Speaker", "Soundbar", "Smartwatch", "43-inch 4K TV",
                  "Thin & Light Laptop", "Wireless Mouse", "Mechanical Keyboard",
                  "DSLR Camera", "Dual-Band WiFi Router", "Party Speaker"],
    },
    "Home & Kitchen": {
        "band": (149, 24999, 50),
        "brands": ["Prestige", "Pigeon", "Milton", "Cello", "Borosil", "Wonderchef",
                   "Hawkins", "Butterfly", "Bajaj"],
        "items": ["Induction Cooktop", "Non-Stick Kadai", "5L Pressure Cooker",
                  "750W Mixer Grinder", "Steel Water Bottle 1L", "18-Piece Dinner Set",
                  "1.5L Electric Kettle", "3-Piece Casserole Set", "Chopper"],
    },
    "Large Appliances": {
        "band": (6990, 74990, 500),
        "brands": ["LG", "Samsung", "Whirlpool", "Voltas", "Godrej", "Haier",
                   "Blue Star", "IFB"],
        "items": ["1.5 Ton Split AC", "Double Door Refrigerator",
                  "Front Load Washing Machine", "Convection Microwave Oven",
                  "Desert Air Cooler", "Dishwasher"],
    },
    "Fashion": {
        "band": (249, 6999, 50),
        "brands": ["Allen Solly", "Peter England", "Levi's", "U.S. Polo Assn.",
                   "Biba", "W for Woman", "Fabindia", "Roadster", "Puma", "Nike",
                   "Woodland", "Bata"],
        "items": ["Cotton Casual Shirt", "Slim Fit Jeans", "Cotton Kurta Set",
                  "Anarkali Kurti", "Running Shoes", "Leather Wallet",
                  "Analog Wrist Watch", "Laptop Backpack", "Cotton T-Shirt"],
    },
    "Beauty & Personal Care": {
        "band": (99, 3499, 10),
        "brands": ["Lakme", "Mamaearth", "Nykaa", "Himalaya", "L'Oreal Paris",
                   "Dot & Key", "Plum", "WOW Skin Science", "Biotique"],
        "items": ["Vitamin C Face Serum", "Sunscreen SPF 50", "Matte Lipstick",
                  "Ubtan Face Wash", "Onion Hair Oil", "Body Lotion 400ml",
                  "Long-Stay Kajal", "Anti-Dandruff Shampoo 650ml"],
    },
    "Grocery & Gourmet": {
        "band": (45, 2499, 5),
        "brands": ["Tata", "Amul", "Aashirvaad", "Fortune", "Nestle", "Britannia",
                   "Haldiram's", "MDH", "Everest", "Saffola"],
        "items": ["Whole Wheat Atta 5kg", "Toor Dal 1kg", "Refined Oil 1L",
                  "Basmati Rice 5kg", "Instant Coffee 200g", "Cow Ghee 1L",
                  "Garam Masala 100g", "Assorted Dry Fruits 500g", "Digestive Biscuits"],
    },
    "Books": {
        "band": (99, 1499, 10),
        "brands": ["Penguin", "HarperCollins", "Rupa", "Westland", "Aleph", "Bloomsbury"],
        "items": ["The Midnight Library (Paperback)", "Wings of Fire (Paperback)",
                  "The Immortals of Meluha (Paperback)", "Atomic Habits (Paperback)",
                  "Ikigai (Hardcover)", "India After Gandhi (Paperback)",
                  "The Palace of Illusions (Paperback)", "Sapiens (Paperback)"],
    },
    "Sports & Fitness": {
        "band": (199, 18999, 50),
        "brands": ["Nivia", "Cosco", "Yonex", "Vector X", "HRX", "Boldfit", "Kore",
                   "Cockatoo"],
        "items": ["6mm Yoga Mat", "Adjustable Dumbbell Set", "Size 5 Football",
                  "Badminton Racket", "Skipping Rope", "Resistance Band Set",
                  "Kashmir Willow Cricket Bat", "Gym Training Gloves"],
    },
    "Toys & Baby": {
        "band": (149, 7999, 10),
        "brands": ["Funskool", "Hot Wheels", "LEGO", "Mattel", "Chicco", "MamyPoko",
                   "LuvLap"],
        "items": ["Building Blocks Set", "Remote Control Car", "Soft Teddy Bear",
                  "Diapers XL (Pack of 64)", "36-Piece Floor Puzzle",
                  "Anti-Colic Feeding Bottle", "Baby Activity Gym", "Family Board Game"],
    },
}
assert set(CATEGORY_WEIGHTS) == set(CATEGORY_CONFIG), "category weights/config out of sync"
CATEGORY_CHOICES = list(CATEGORY_WEIGHTS.keys())
CATEGORY_CHOICE_WEIGHTS = list(CATEGORY_WEIGHTS.values())

ORDER_STATUSES = ["PLACED", "SHIPPED", "DELIVERED", "CANCELLED", "RETURNED"]
ORDER_STATUS_WEIGHTS = [15, 20, 45, 12, 8]
# UPI-dominant, the way real Indian consumer payments break down.
PAYMENT_METHODS = ["CREDIT_CARD", "DEBIT_CARD", "UPI", "NET_BANKING", "WALLET", "COD"]
PAYMENT_METHOD_WEIGHTS = [12, 8, 58, 7, 7, 8]
PAYMENT_STATUSES = ["SUCCESS", "FAILED", "PENDING", "REFUNDED"]

CUSTOMER_COLUMNS = ["customer_id", "full_name", "email", "city", "state", "signup_date"]
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


def generate_customers(rng: random.Random) -> list:
    city_choices = [(c, s) for c, s, _ in CITY_STATE_WEIGHTS]
    city_weights = [w for _, _, w in CITY_STATE_WEIGHTS]
    used_emails: set = set()
    rows = []
    for i in range(1, N_CUSTOMERS + 1):
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        city, state = rng.choices(city_choices, weights=city_weights)[0]

        handle = f"{first}.{last}".lower()
        email = f"{handle}@{rng.choice(EMAIL_DOMAINS)}"
        while email in used_emails:
            email = f"{handle}{rng.randint(1, 9999)}@{rng.choice(EMAIL_DOMAINS)}"
        used_emails.add(email)

        rows.append(
            {
                "customer_id": f"C{i:05d}",
                "full_name": f"{first} {last}",
                "email": email,
                "city": city,
                "state": state,
                "signup_date": random_date(rng, SIGNUP_START, DATASET_AS_OF).isoformat(),
            }
        )
    return rows


def _skewed_price(rng: random.Random, band: tuple) -> float:
    """A price inside (low, high), drawn on `step` and skewed hard towards
    the low end -- most items in a category cost far less than its
    ceiling."""
    low, high, step = band
    fraction = rng.random() ** 3
    raw = low + (high - low) * fraction
    stepped = round(raw / step) * step
    return float(min(max(stepped, low), high))


def generate_products(rng: random.Random) -> list:
    used_names: set = set()
    rows = []
    for i in range(1, N_PRODUCTS + 1):
        category = rng.choices(CATEGORY_CHOICES, weights=CATEGORY_CHOICE_WEIGHTS)[0]
        config = CATEGORY_CONFIG[category]
        brand = rng.choice(config["brands"])
        item = rng.choice(config["items"])

        name = f"{brand} {item}"
        while name in used_names:
            name = f"{brand} {item} ({rng.choice(['2024', '2025', 'Pro', 'Plus', 'Lite', 'Max'])})"
        used_names.add(name)

        price = _skewed_price(rng, config["band"])
        rows.append(
            {
                "product_id": f"P{i:04d}",
                "product_name": name,
                "category": category,
                "price": round(price, 2),
            }
        )
    return rows


def _order_date(rng: random.Random, signup: date) -> date:
    # Bias orders towards the recent past so month-over-month charts show
    # live-looking activity, while still leaving a long tail of history.
    if rng.random() < 0.4:
        start = max(signup, DATASET_AS_OF - timedelta(days=365))
    else:
        start = max(signup, DATASET_AS_OF - timedelta(days=730))
    return random_date(rng, start, DATASET_AS_OF)


def generate_orders(rng: random.Random, customers: list) -> list:
    rows = []
    for i in range(1, N_ORDERS + 1):
        customer = rng.choice(customers)
        signup = date.fromisoformat(customer["signup_date"])
        rows.append(
            {
                "order_id": f"O{i:06d}",
                "customer_id": customer["customer_id"],
                "order_date": _order_date(rng, signup).isoformat(),
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
                "quantity": rng.choices([1, 2, 3, 4], weights=[55, 28, 12, 5])[0],
                # Price at time of order -- intentionally independent of
                # (but close to) the product's current list price.
                "unit_price": round(product["price"] * rng.uniform(0.92, 1.05), 2),
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
                "payment_method": rng.choices(PAYMENT_METHODS, weights=PAYMENT_METHOD_WEIGHTS)[0],
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
                    "payment_method": rng.choices(PAYMENT_METHODS, weights=PAYMENT_METHOD_WEIGHTS)[0],
                    "payment_status": "SUCCESS",
                    "amount": order["total_amount"],
                }
            )
    return rows


# ---------------------------------------------------------------------------
# Deliberate, bounded defect injection -- one defect type per selected row,
# each mapped directly to a documented Phase 2/3 validation rule.
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

    print(f"Generating synthetic India e-commerce dataset (seed={SEED})...")

    customers = generate_customers(rng)
    products = generate_products(rng)
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
