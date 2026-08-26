"""Entity-level, referential, and temporal validation rules.

Implements the approved Phase 2/3 data-quality contract: required fields,
primary-key uniqueness, foreign-key integrity, enum/domain rules, numeric
rules, date validity, and cross-entity temporal ordering.

Each validate_* function returns a violations map:
    {row_index: [{"code": str, "message": str}, ...]}
A row that breaks several rules keeps every applicable entry -- nothing is
collapsed down to a single "primary" reason.
"""

from datetime import datetime, timezone

import pandas as pd

from src.validation.checks import (
    EMAIL_PATTERN,
    ViolationCollector,
    duplicated_nonblank,
    is_blank,
    to_dates,
    to_numeric,
)

ORDER_STATUSES = {"PLACED", "SHIPPED", "DELIVERED", "CANCELLED", "RETURNED"}
PAYMENT_METHODS = {"CREDIT_CARD", "DEBIT_CARD", "UPI", "NET_BANKING", "WALLET", "COD"}
PAYMENT_STATUSES = {"SUCCESS", "FAILED", "PENDING", "REFUNDED"}


def _today() -> pd.Timestamp:
    # Wall-clock "now", not a constant tied to how the sample data happens
    # to have been generated -- a real pipeline has no other honest anchor
    # for "is this date in the future".
    return pd.Timestamp(datetime.now(timezone.utc).date())


def validate_customers(df: pd.DataFrame) -> dict:
    c = ViolationCollector(df)

    c.flag(is_blank(df["customer_id"]), "MISSING_CUSTOMER_ID", "customer_id is required")
    c.flag(is_blank(df["full_name"]), "MISSING_FULL_NAME", "full_name is required")
    c.flag(is_blank(df["city"]), "MISSING_CITY", "city is required")
    c.flag(is_blank(df["country"]), "MISSING_COUNTRY", "country is required")
    c.flag(duplicated_nonblank(df["customer_id"]), "DUPLICATE_CUSTOMER_ID", "duplicate customer_id")

    email_blank = is_blank(df["email"])
    c.flag(email_blank, "MISSING_EMAIL", "email is required")
    c.flag(
        ~email_blank & ~df["email"].str.match(EMAIL_PATTERN),
        "INVALID_EMAIL_FORMAT",
        "email is not a valid format",
    )

    date_blank = is_blank(df["signup_date"])
    c.flag(date_blank, "MISSING_SIGNUP_DATE", "signup_date is required")
    parsed = to_dates(df["signup_date"])
    c.flag(~date_blank & parsed.isna(), "INVALID_SIGNUP_DATE", "signup_date is not a valid date")
    c.flag(parsed.notna() & (parsed > _today()), "FUTURE_SIGNUP_DATE", "signup_date is in the future")

    return c.violations


def validate_products(df: pd.DataFrame) -> dict:
    c = ViolationCollector(df)

    c.flag(is_blank(df["product_id"]), "MISSING_PRODUCT_ID", "product_id is required")
    c.flag(is_blank(df["product_name"]), "MISSING_PRODUCT_NAME", "product_name is required")
    c.flag(is_blank(df["category"]), "MISSING_CATEGORY", "category is required")
    c.flag(duplicated_nonblank(df["product_id"]), "DUPLICATE_PRODUCT_ID", "duplicate product_id")

    price_blank = is_blank(df["price"])
    c.flag(price_blank, "MISSING_PRICE", "price is required")
    price = to_numeric(df["price"])
    c.flag(~price_blank & price.isna(), "NON_NUMERIC_PRICE", "price is not numeric")
    c.flag(price.notna() & (price < 0), "NEGATIVE_PRICE", "price must not be negative")

    return c.violations


def validate_orders(df: pd.DataFrame, customers_df: pd.DataFrame) -> dict:
    c = ViolationCollector(df)

    c.flag(is_blank(df["order_id"]), "MISSING_ORDER_ID", "order_id is required")
    c.flag(duplicated_nonblank(df["order_id"]), "DUPLICATE_ORDER_ID", "duplicate order_id")

    customer_blank = is_blank(df["customer_id"])
    c.flag(customer_blank, "MISSING_ORDER_CUSTOMER_ID", "customer_id is required")

    valid_customer_ids = set(customers_df.loc[~is_blank(customers_df["customer_id"]), "customer_id"])
    c.flag(
        ~customer_blank & ~df["customer_id"].isin(valid_customer_ids),
        "INVALID_CUSTOMER_FK",
        "customer_id does not exist in customers",
    )

    date_blank = is_blank(df["order_date"])
    c.flag(date_blank, "MISSING_ORDER_DATE", "order_date is required")
    order_dates = to_dates(df["order_date"])
    c.flag(~date_blank & order_dates.isna(), "INVALID_ORDER_DATE", "order_date is not a valid date")
    c.flag(order_dates.notna() & (order_dates > _today()), "FUTURE_ORDER_DATE", "order_date is in the future")

    status_blank = is_blank(df["status"])
    c.flag(status_blank, "MISSING_ORDER_STATUS", "status is required")
    c.flag(
        ~status_blank & ~df["status"].isin(ORDER_STATUSES),
        "INVALID_ORDER_STATUS",
        "status is not a recognized value",
    )

    total_blank = is_blank(df["total_amount"])
    c.flag(total_blank, "MISSING_TOTAL_AMOUNT", "total_amount is required")
    total = to_numeric(df["total_amount"])
    c.flag(~total_blank & total.isna(), "NON_NUMERIC_TOTAL_AMOUNT", "total_amount is not numeric")
    c.flag(total.notna() & (total < 0), "NEGATIVE_TOTAL_AMOUNT", "total_amount must not be negative")

    # Temporal: order_date must not precede the referenced customer's signup_date.
    signup_by_customer = customers_df.set_index("customer_id")["signup_date"]
    signup_by_customer = signup_by_customer[~signup_by_customer.index.duplicated(keep="first")]
    matched_signup = df["customer_id"].map(signup_by_customer)
    signup_dates = to_dates(matched_signup)
    valid_pair = order_dates.notna() & signup_dates.notna()
    c.flag(
        valid_pair & (order_dates < signup_dates),
        "ORDER_DATE_BEFORE_CUSTOMER_SIGNUP",
        "order_date precedes the customer's signup_date",
    )

    return c.violations


def validate_order_items(df: pd.DataFrame, orders_df: pd.DataFrame, products_df: pd.DataFrame) -> dict:
    c = ViolationCollector(df)

    c.flag(is_blank(df["order_item_id"]), "MISSING_ORDER_ITEM_ID", "order_item_id is required")
    c.flag(duplicated_nonblank(df["order_item_id"]), "DUPLICATE_ORDER_ITEM_ID", "duplicate order_item_id")

    order_blank = is_blank(df["order_id"])
    c.flag(order_blank, "MISSING_ORDER_ITEM_ORDER_ID", "order_id is required")
    valid_order_ids = set(orders_df.loc[~is_blank(orders_df["order_id"]), "order_id"])
    c.flag(
        ~order_blank & ~df["order_id"].isin(valid_order_ids),
        "INVALID_ORDER_FK",
        "order_id does not exist in orders",
    )

    product_blank = is_blank(df["product_id"])
    c.flag(product_blank, "MISSING_ORDER_ITEM_PRODUCT_ID", "product_id is required")
    valid_product_ids = set(products_df.loc[~is_blank(products_df["product_id"]), "product_id"])
    c.flag(
        ~product_blank & ~df["product_id"].isin(valid_product_ids),
        "INVALID_PRODUCT_FK",
        "product_id does not exist in products",
    )

    qty_blank = is_blank(df["quantity"])
    c.flag(qty_blank, "MISSING_QUANTITY", "quantity is required")
    qty = to_numeric(df["quantity"])
    c.flag(~qty_blank & qty.isna(), "NON_NUMERIC_QUANTITY", "quantity is not numeric")
    c.flag(qty.notna() & (qty <= 0), "INVALID_QUANTITY", "quantity must be greater than zero")

    price_blank = is_blank(df["unit_price"])
    c.flag(price_blank, "MISSING_UNIT_PRICE", "unit_price is required")
    price = to_numeric(df["unit_price"])
    c.flag(~price_blank & price.isna(), "NON_NUMERIC_UNIT_PRICE", "unit_price is not numeric")
    c.flag(price.notna() & (price <= 0), "INVALID_UNIT_PRICE", "unit_price must be greater than zero")

    return c.violations


def validate_payments(df: pd.DataFrame, orders_df: pd.DataFrame) -> dict:
    c = ViolationCollector(df)

    c.flag(is_blank(df["payment_id"]), "MISSING_PAYMENT_ID", "payment_id is required")
    c.flag(duplicated_nonblank(df["payment_id"]), "DUPLICATE_PAYMENT_ID", "duplicate payment_id")

    order_blank = is_blank(df["order_id"])
    c.flag(order_blank, "MISSING_PAYMENT_ORDER_ID", "order_id is required")
    valid_order_ids = set(orders_df.loc[~is_blank(orders_df["order_id"]), "order_id"])
    c.flag(
        ~order_blank & ~df["order_id"].isin(valid_order_ids),
        "INVALID_ORDER_FK",
        "order_id does not exist in orders",
    )

    date_blank = is_blank(df["payment_date"])
    c.flag(date_blank, "MISSING_PAYMENT_DATE", "payment_date is required")
    payment_dates = to_dates(df["payment_date"])
    c.flag(~date_blank & payment_dates.isna(), "INVALID_PAYMENT_DATE", "payment_date is not a valid date")
    c.flag(
        payment_dates.notna() & (payment_dates > _today()),
        "FUTURE_PAYMENT_DATE",
        "payment_date is in the future",
    )

    method_blank = is_blank(df["payment_method"])
    c.flag(method_blank, "MISSING_PAYMENT_METHOD", "payment_method is required")
    c.flag(
        ~method_blank & ~df["payment_method"].isin(PAYMENT_METHODS),
        "INVALID_PAYMENT_METHOD",
        "payment_method is not a recognized value",
    )

    status_blank = is_blank(df["payment_status"])
    c.flag(status_blank, "MISSING_PAYMENT_STATUS", "payment_status is required")
    c.flag(
        ~status_blank & ~df["payment_status"].isin(PAYMENT_STATUSES),
        "INVALID_PAYMENT_STATUS",
        "payment_status is not a recognized value",
    )

    amount_blank = is_blank(df["amount"])
    c.flag(amount_blank, "MISSING_AMOUNT", "amount is required")
    amount = to_numeric(df["amount"])
    c.flag(~amount_blank & amount.isna(), "NON_NUMERIC_AMOUNT", "amount is not numeric")
    c.flag(amount.notna() & (amount < 0), "NEGATIVE_AMOUNT", "amount must not be negative")

    # Temporal: payment_date must not precede the referenced order's order_date.
    order_date_by_order = orders_df.set_index("order_id")["order_date"]
    order_date_by_order = order_date_by_order[~order_date_by_order.index.duplicated(keep="first")]
    matched_order_date = df["order_id"].map(order_date_by_order)
    order_dates = to_dates(matched_order_date)
    valid_pair = payment_dates.notna() & order_dates.notna()
    c.flag(
        valid_pair & (payment_dates < order_dates),
        "PAYMENT_DATE_BEFORE_ORDER_DATE",
        "payment_date precedes the order's order_date",
    )

    return c.violations
