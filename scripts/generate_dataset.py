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
# rarer but no longer vanishingly thin, so the order-value distribution
# looks like real consumer e-commerce (lots of small orders, a long tail
# of expensive ones).
CATEGORY_WEIGHTS = {
    "Grocery & Gourmet": 22,
    "Fashion": 20,
    "Beauty & Personal Care": 16,
    "Home & Kitchen": 12,
    "Books": 10,
    "Toys & Baby": 8,
    "Electronics": 6,
    "Mobile Accessories": 6,
    "Sports & Fitness": 6,
    "Smartphones": 4,
    "Large Appliances": 4,
}

# Each category is a list of *product-line groups*. A group pairs a set of
# brands that actually make that kind of thing with the item names they
# make, and gives that line its own tight INR band (low, high, step) --
# so "Boult" (an audio brand) can never be attached to "Thin & Light
# Laptop", and a split AC can never be priced like a phone case. Prices
# are drawn on the step so they read like real MRPs, and skewed towards
# the low end of each band (see _skewed_price) so a line's typical item
# is cheap even when its ceiling is high. This is the same principle the
# Smartphones / Mobile Accessories split already used, applied
# throughout.
CATEGORY_CONFIG = {
    "Smartphones": [
        {
            # Budget / mid-range: the volume tier. Brands here that also
            # make flagships (Samsung, vivo, OPPO) keep their budget lines
            # in this band; brands that never cross ~45k stay only here.
            "band": (6499, 44990, 100),
            "brands": ["Redmi", "realme", "POCO", "Motorola", "Samsung", "vivo",
                       "OPPO", "Lava", "Infinix", "iQOO"],
            "items": ["5G Smartphone", "Smartphone"],
        },
        {
            # Premium / flagship. Only brands that genuinely sell 40k+
            # phones in India -- so a price near the ceiling never lands on
            # a budget brand.
            "band": (39990, 149900, 500),
            "brands": ["Samsung", "Apple", "OnePlus", "Xiaomi", "vivo", "OPPO", "Nothing"],
            "items": ["5G Smartphone", "Flagship Smartphone"],
        },
    ],
    "Mobile Accessories": [
        {
            "band": (699, 3999, 50),  # audio
            "brands": ["boAt", "Noise", "Boult", "pTron", "Zebronics", "realme"],
            "items": ["Wireless Earbuds", "Bluetooth Neckband", "Over-Ear Headphones"],
        },
        {
            "band": (799, 3499, 50),  # power banks
            "brands": ["Ambrane", "Mi", "URBN", "Stuffcool", "Duracell"],
            "items": ["10000mAh Power Bank", "20000mAh Power Bank"],
        },
        {
            "band": (149, 1799, 50),  # chargers & cables
            "brands": ["Ambrane", "Mi", "Portronics", "Stuffcool", "boAt", "Wingle"],
            "items": ["33W Fast Charger", "65W GaN Charger", "USB-C Cable (1.5m)",
                      "Car Phone Charger", "3-in-1 Charging Cable"],
        },
        {
            "band": (149, 1299, 50),  # protection
            "brands": ["Spigen", "Ringke", "Stuffcool", "GoBhaarat"],
            "items": ["Tempered Glass (Pack of 2)", "Silicone Back Cover", "Rugged Phone Case"],
        },
    ],
    "Electronics": [
        {
            "band": (1990, 27999, 100),  # home audio
            "brands": ["Sony", "JBL", "boAt", "Zebronics", "Philips", "Marshall"],
            "items": ["Bluetooth Party Speaker", "Soundbar", "Portable Bluetooth Speaker",
                      "Bookshelf Speaker Pair"],
        },
        {
            "band": (26990, 119900, 500),  # laptops (monitors are a separate tier -- kept out)
            "brands": ["HP", "Dell", "Lenovo", "Acer", "ASUS"],
            "items": ["Thin & Light Laptop", "Gaming Laptop", "2-in-1 Laptop"],
        },
        {
            "band": (499, 5999, 50),  # PC peripherals
            "brands": ["Logitech", "HP", "Portronics", "Zebronics", "Dell"],
            "items": ["Wireless Mouse", "Mechanical Keyboard", "Keyboard & Mouse Combo", "1080p Webcam"],
        },
        {
            "band": (10990, 22990, 500),  # HD / Full-HD televisions (smaller screens)
            "brands": ["Samsung", "LG", "TCL", "Xiaomi", "Kodak", "Acer"],
            "items": ["32-inch HD LED TV", "40-inch Full HD LED TV"],
        },
        {
            "band": (24990, 74990, 500),  # 4K smart televisions (larger screens)
            "brands": ["Samsung", "LG", "Sony", "TCL", "Xiaomi", "OnePlus"],
            "items": ["43-inch 4K Smart TV", "50-inch 4K Smart TV", "55-inch 4K Smart TV"],
        },
        {
            "band": (999, 19999, 100),  # smartwatches -- budget Noise to Galaxy Watch, name implies no tier
            "brands": ["Noise", "boAt", "Fire-Boltt", "Amazfit", "Samsung"],
            "items": ["Smartwatch"],
        },
        {
            "band": (24990, 89990, 500),  # cameras
            "brands": ["Canon", "Nikon", "Sony", "GoPro"],
            "items": ["DSLR Camera (with Kit Lens)", "Mirrorless Camera", "Action Camera"],
        },
        {
            "band": (999, 7999, 100),  # networking
            "brands": ["TP-Link", "D-Link", "Tenda", "Mercusys"],
            "items": ["Dual-Band WiFi Router", "WiFi Range Extender", "Mesh WiFi System (2-pack)"],
        },
    ],
    "Large Appliances": [
        {
            "band": (23990, 54990, 500),  # air conditioners -- generic name, no tonnage tier
            "brands": ["LG", "Samsung", "Voltas", "Daikin", "Blue Star", "Lloyd", "Hitachi"],
            "items": ["Split AC", "Window AC", "Inverter Split AC"],
        },
        {
            "band": (12990, 36990, 500),  # refrigerators (single/double door)
            "brands": ["LG", "Samsung", "Whirlpool", "Godrej", "Haier"],
            "items": ["Single Door Refrigerator", "Double Door Refrigerator"],
        },
        {
            "band": (42990, 94990, 1000),  # premium refrigerators
            "brands": ["LG", "Samsung", "Bosch", "Haier"],
            "items": ["Side-by-Side Refrigerator", "French Door Refrigerator"],
        },
        {
            "band": (9490, 22990, 500),  # top-load / semi-automatic washing machines
            "brands": ["LG", "Samsung", "Whirlpool", "Godrej", "Panasonic"],
            "items": ["Semi-Automatic Washing Machine", "Top Load Washing Machine"],
        },
        {
            "band": (23990, 52990, 500),  # front-load washing machines
            "brands": ["LG", "Samsung", "Bosch", "IFB"],
            "items": ["Front Load Washing Machine"],
        },
        {
            "band": (5490, 18990, 100),  # microwave ovens
            "brands": ["IFB", "LG", "Samsung", "Panasonic", "Godrej"],
            "items": ["Solo Microwave Oven", "Grill Microwave Oven", "Convection Microwave Oven"],
        },
        {
            "band": (4990, 15990, 100),  # air coolers
            "brands": ["Symphony", "Bajaj", "Crompton", "Orient", "Havells"],
            "items": ["Desert Air Cooler", "Tower Air Cooler", "Personal Air Cooler"],
        },
        {
            "band": (17990, 46990, 500),  # dishwashers & freezers
            "brands": ["IFB", "Bosch", "LG", "Voltas Beko"],
            "items": ["Dishwasher (13 Place Settings)", "Chest Freezer 200L"],
        },
    ],
    "Home & Kitchen": [
        {
            "band": (399, 2999, 50),  # cookware -- single pieces + pressure cookers
            "brands": ["Prestige", "Hawkins", "Pigeon", "Butterfly", "Wonderchef", "Vinod"],
            "items": ["5L Pressure Cooker", "3L Pressure Cooker", "Non-Stick Kadai",
                      "Non-Stick Frying Pan", "Non-Stick Dosa Tawa"],
        },
        {
            "band": (899, 5999, 50),  # kitchen appliances -- mixer/cooktop tier
            "brands": ["Prestige", "Bajaj", "Philips", "Pigeon", "Havells", "Wonderchef"],
            "items": ["Induction Cooktop", "750W Mixer Grinder", "Hand Blender",
                      "Food Processor", "Electric Chopper"],
        },
        {
            "band": (549, 2499, 50),  # kitchen appliances -- kettle/toaster tier
            "brands": ["Prestige", "Bajaj", "Philips", "Pigeon", "Borosil"],
            "items": ["1.5L Electric Kettle", "2-Slice Pop-up Toaster", "Sandwich Maker",
                      "Hand Mixer"],
        },
        {
            "band": (549, 3999, 50),  # dinnerware
            "brands": ["Cello", "Borosil", "La Opala", "Larah", "Milton"],
            "items": ["18-Piece Dinner Set", "Opalware Dinner Set (18-Piece)", "6-Piece Dinner Plate Set"],
        },
        {
            "band": (149, 1999, 50),  # drinkware & storage
            "brands": ["Cello", "Milton", "Borosil", "Treo", "Signoraware"],
            "items": ["Steel Water Bottle 1L", "6-Piece Glass Tumbler Set", "Glass Storage Container Set",
                      "3-Piece Casserole Set", "Insulated Lunch Box"],
        },
    ],
    "Fashion": [
        {
            "band": (499, 2999, 50),  # western apparel
            "brands": ["Allen Solly", "Peter England", "Levi's", "U.S. Polo Assn.",
                       "Roadster", "Wrangler", "Van Heusen"],
            "items": ["Cotton Casual Shirt", "Slim Fit Jeans", "Cotton T-Shirt",
                      "Chino Trousers", "Polo T-Shirt"],
        },
        {
            "band": (699, 4999, 50),  # ethnic wear
            "brands": ["Biba", "W for Woman", "Fabindia", "Libas", "Aurelia", "Manyavar"],
            "items": ["Anarkali Kurti", "Cotton Kurta Set", "Straight Kurta",
                      "Palazzo Set", "Nehru Jacket"],
        },
        {
            "band": (799, 6999, 50),  # footwear
            "brands": ["Nike", "Puma", "Adidas", "Woodland", "Bata", "Campus", "Red Chief", "Sparx"],
            "items": ["Running Shoes", "Casual Sneakers", "Leather Formal Shoes",
                      "Sports Sandals", "Canvas Shoes"],
        },
        {
            "band": (399, 3999, 50),  # accessories & bags
            "brands": ["Wildcraft", "American Tourister", "Skybags", "Fastrack",
                       "Titan", "Hidesign", "Baggit"],
            "items": ["Laptop Backpack", "Analog Wrist Watch", "Leather Wallet",
                      "Sling Bag", "Sunglasses"],
        },
    ],
    "Beauty & Personal Care": [
        {
            "band": (149, 1499, 10),  # skincare
            "brands": ["Mamaearth", "Minimalist", "Dot & Key", "Plum", "WOW Skin Science",
                       "Himalaya", "The Derma Co"],
            "items": ["Vitamin C Face Serum", "Sunscreen SPF 50", "Ubtan Face Wash",
                      "Niacinamide Serum", "Moisturiser 100ml", "Under-Eye Cream"],
        },
        {
            "band": (99, 1999, 10),  # makeup
            "brands": ["Lakme", "Maybelline", "L'Oreal Paris", "Sugar", "Nykaa", "Colorbar"],
            "items": ["Matte Lipstick", "Long-Stay Kajal", "Compact Powder",
                      "Liquid Foundation", "Mascara", "Nail Polish"],
        },
        {
            "band": (99, 999, 10),  # hair & body care
            "brands": ["Mamaearth", "WOW Skin Science", "L'Oreal Paris", "Dove", "Biotique", "Parachute"],
            "items": ["Onion Hair Oil", "Anti-Dandruff Shampoo 650ml", "Body Lotion 400ml",
                      "Hair Serum", "Conditioner 340ml", "Body Wash 250ml"],
        },
        {
            "band": (99, 599, 10),  # fragrance -- budget deo sprays and body perfumes
            "brands": ["Wild Stone", "Fogg", "Engage", "Denver", "Nivea Men", "Set Wet"],
            "items": ["Perfume Body Spray", "Deodorant Body Spray", "Pocket Perfume 18ml"],
        },
        {
            "band": (149, 899, 10),  # men's grooming products
            "brands": ["Beardo", "The Man Company", "Bombay Shaving Company", "Ustraa"],
            "items": ["Beard Oil", "Beard Wash", "Face Scrub for Men", "Charcoal Face Wash"],
        },
    ],
    "Grocery & Gourmet": [
        {
            "band": (60, 899, 5),  # staples
            "brands": ["Aashirvaad", "Tata Sampann", "Fortune", "India Gate", "Daawat", "Organic Tattva"],
            "items": ["Whole Wheat Atta 5kg", "Toor Dal 1kg", "Basmati Rice 5kg",
                      "Sona Masoori Rice 5kg", "Besan 1kg", "Poha 500g"],
        },
        {
            "band": (120, 799, 5),  # cooking oil & ghee
            "brands": ["Fortune", "Saffola", "Dhara", "Amul", "Patanjali", "Nature Fresh"],
            "items": ["Refined Sunflower Oil 1L", "Mustard Oil 1L", "Cow Ghee 1L", "Groundnut Oil 1L"],
        },
        {
            "band": (35, 349, 5),  # spices & condiments
            "brands": ["MDH", "Everest", "Catch", "Tata Sampann", "Aachi"],
            "items": ["Garam Masala 100g", "Turmeric Powder 200g", "Red Chilli Powder 200g",
                      "Chana Masala 100g", "Kitchen King Masala 100g"],
        },
        {
            "band": (25, 999, 5),  # packaged & snacks
            "brands": ["Britannia", "Parle", "Haldiram's", "Nestle", "Amul", "Mother Dairy", "Bikano"],
            "items": ["Digestive Biscuits", "Namkeen Mix 400g", "Instant Coffee 200g",
                      "Chocolate Bar (Pack of 5)", "Cheese Slices 200g", "Roasted Almonds 500g"],
        },
    ],
    "Books": [
        {
            "band": (99, 1499, 10),
            "brands": ["Penguin", "HarperCollins", "Rupa", "Westland", "Aleph",
                       "Bloomsbury", "Scholastic", "Arihant"],
            "items": ["Fiction Bestseller (Paperback)", "Literary Novel (Paperback)",
                      "Self-Help Bestseller (Paperback)", "Business & Economics (Paperback)",
                      "Indian History (Hardcover)", "Biography (Hardcover)",
                      "Children's Illustrated Book", "Competitive Exam Guide"],
        },
    ],
    "Sports & Fitness": [
        {
            "band": (149, 1499, 10),  # fitness accessories
            "brands": ["HRX", "Boldfit", "Kore", "Aurion", "Amazon Basics", "Cult.sport"],
            "items": ["6mm Yoga Mat", "Skipping Rope", "Resistance Band Set",
                      "Gym Training Gloves", "Push-up Bar Set", "Foam Roller"],
        },
        {
            "band": (999, 8999, 100),  # weights & strength equipment
            "brands": ["Kore", "Cockatoo", "Aurion", "PowerMax", "Lifelong"],
            "items": ["Adjustable Dumbbell Set 20kg", "Kettlebell 8kg",
                      "Cast Iron Dumbbell Pair 10kg", "Home Gym Bench"],
        },
        {
            "band": (299, 4999, 50),  # team & racket sports (Kashmir-willow tier, not English willow)
            "brands": ["Nivia", "Cosco", "Yonex", "Vector X", "SG", "SS", "Li-Ning"],
            "items": ["Football (Size 5)", "Badminton Racket", "Cricket Bat (Kashmir Willow)",
                      "Volleyball", "Cricket Leather Ball", "Table Tennis Racket Set"],
        },
        {
            "band": (4990, 18999, 100),  # cardio equipment
            "brands": ["PowerMax", "Lifelong", "Fitkit", "Cult.sport"],
            "items": ["Magnetic Exercise Bike", "Manual Treadmill", "Stepper with Resistance Bands"],
        },
    ],
    "Toys & Baby": [
        {
            "band": (199, 4999, 50),  # toys & games
            "brands": ["Funskool", "Hot Wheels", "LEGO", "Mattel", "Hasbro", "Spin Master", "Skillmatics"],
            "items": ["Building Blocks Set", "Remote Control Car", "Floor Puzzle (36-Piece)",
                      "Family Board Game", "Action Figure", "Educational Activity Kit",
                      "Toy Car Set"],
        },
        {
            "band": (199, 1999, 50),  # plush & soft toys
            "brands": ["Dimpy Stuff", "Miss & Chief", "Wild Republic", "Hallmark"],
            "items": ["Soft Teddy Bear", "Plush Animal Toy", "Cushion Soft Toy"],
        },
        {
            "band": (99, 999, 10),  # baby consumables
            "brands": ["MamyPoko", "Pampers", "Huggies", "Johnson's", "Himalaya", "Mamaearth"],
            "items": ["Diapers XL (Pack of 64)", "Baby Wipes (Pack of 3)", "Baby Lotion 200ml",
                      "Baby Powder 400g", "Diaper Rash Cream"],
        },
        {
            "band": (349, 3999, 50),  # baby gear
            "brands": ["Chicco", "LuvLap", "Philips Avent", "R for Rabbit", "Mee Mee"],
            "items": ["Anti-Colic Feeding Bottle", "Baby Activity Gym", "Baby Carrier",
                      "Sterilizer & Warmer", "Baby Walker"],
        },
    ],
}
assert set(CATEGORY_WEIGHTS) == set(CATEGORY_CONFIG), "category weights/config out of sync"
for _cat, _groups in CATEGORY_CONFIG.items():
    assert _groups and all({"band", "brands", "items"} <= set(g) for g in _groups), _cat

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


MIN_PRODUCTS_PER_CATEGORY = 3


def _category_sequence(rng: random.Random) -> list:
    """A deterministic list of N_PRODUCTS category labels whose composition
    follows CATEGORY_WEIGHTS (largest-remainder apportionment), with a hard
    floor of MIN_PRODUCTS_PER_CATEGORY so no category -- big-ticket ones
    especially -- ever ends up with one or two SKUs by chance. Shuffled so
    product ids interleave categories rather than run in blocks."""
    total_w = sum(CATEGORY_WEIGHTS.values())
    exact = {c: w / total_w * N_PRODUCTS for c, w in CATEGORY_WEIGHTS.items()}
    quota = {c: int(v) for c, v in exact.items()}
    for c in sorted(exact, key=lambda c: exact[c] - int(exact[c]), reverse=True)[
        : N_PRODUCTS - sum(quota.values())
    ]:
        quota[c] += 1
    for c in CATEGORY_WEIGHTS:
        while quota[c] < MIN_PRODUCTS_PER_CATEGORY:
            donor = max(CATEGORY_WEIGHTS, key=lambda d: quota[d])
            quota[donor] -= 1
            quota[c] += 1
    sequence = [c for c, n in quota.items() for _ in range(n)]
    rng.shuffle(sequence)
    return sequence


def generate_products(rng: random.Random) -> list:
    used_names: set = set()
    rows = []
    categories = _category_sequence(rng)
    for i in range(1, N_PRODUCTS + 1):
        category = categories[i - 1]
        group = rng.choice(CATEGORY_CONFIG[category])
        brand = rng.choice(group["brands"])
        item = rng.choice(group["items"])

        name = f"{brand} {item}"
        while name in used_names:
            name = f"{brand} {item} ({rng.choice(['2024', '2025', 'Pro', 'Plus', 'Lite', 'Max'])})"
        used_names.add(name)

        price = _skewed_price(rng, group["band"])
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
    """Every order gets at least one line item (a real marketplace order
    always has one), then the remaining items -- keeping the total at
    exactly N_ORDER_ITEMS -- are distributed randomly across orders, so
    baskets still vary in size. No filler rows: the same 5000 items, just
    guaranteed to cover every order first.

    Which product a line item is for is weighted down for pricier items
    (weight ~ price**-0.3): an everyday ~100-rupee staple sells many more
    units than a 60,000-rupee phone, so most baskets stay small and the
    order-value distribution keeps its realistic shape even though the
    catalogue now has a proper big-ticket tail. Quantity leans to 1-2."""
    pick_weights = [1.0 / (max(p["price"], 1.0) ** 0.3) for p in products]
    seq = 0

    def make_item(order: dict) -> dict:
        nonlocal seq
        seq += 1
        product = rng.choices(products, weights=pick_weights)[0]
        return {
            "order_item_id": f"OI{seq:07d}",
            "order_id": order["order_id"],
            "product_id": product["product_id"],
            "quantity": rng.choices([1, 2, 3, 4], weights=[55, 28, 12, 5])[0],
            # Price at time of order -- intentionally independent of (but
            # close to) the product's current list price.
            "unit_price": round(product["price"] * rng.uniform(0.92, 1.05), 2),
        }

    rows = [make_item(order) for order in orders]
    for _ in range(max(0, N_ORDER_ITEMS - len(orders))):
        rows.append(make_item(rng.choice(orders)))
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
