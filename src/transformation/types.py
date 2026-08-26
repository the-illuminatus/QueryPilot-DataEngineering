"""Casts validated string columns into proper analytical types.

Input here has already passed Phase 3 validation, so every value is
expected to parse cleanly. A parse failure at this stage means the
accepted-row output and the validation rules that produced it have
drifted out of sync -- a pipeline bug, not an ordinary data-quality
outcome -- so these functions raise loudly rather than coercing or
dropping anything.
"""

import pandas as pd

ORDER_STATUS_CATEGORIES = ["PLACED", "SHIPPED", "DELIVERED", "CANCELLED", "RETURNED"]
PAYMENT_METHOD_CATEGORIES = ["CREDIT_CARD", "DEBIT_CARD", "UPI", "NET_BANKING", "WALLET", "COD"]
PAYMENT_STATUS_CATEGORIES = ["SUCCESS", "FAILED", "PENDING", "REFUNDED"]


class TransformationTypeError(Exception):
    """Raised when a value that passed Phase 3 validation still fails to
    parse here."""


def _parse_dates(series: pd.Series, column: str) -> pd.Series:
    parsed = pd.to_datetime(series, errors="coerce")
    if parsed.isna().any():
        bad = series[parsed.isna()]
        raise TransformationTypeError(
            f"{column}: {len(bad)} value(s) failed to parse as dates despite "
            f"having passed validation: {list(bad.head(3))}"
        )
    return parsed


def _parse_numeric(series: pd.Series, column: str) -> pd.Series:
    parsed = pd.to_numeric(series, errors="coerce")
    if parsed.isna().any():
        bad = series[parsed.isna()]
        raise TransformationTypeError(
            f"{column}: {len(bad)} value(s) failed to parse as numeric despite "
            f"having passed validation: {list(bad.head(3))}"
        )
    return parsed


def cast_customers(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["signup_date"] = _parse_dates(out["signup_date"], "signup_date")
    return out


def cast_products(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["price"] = _parse_numeric(out["price"], "price")
    return out


def cast_orders(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["order_date"] = _parse_dates(out["order_date"], "order_date")
    out["status"] = pd.Categorical(out["status"], categories=ORDER_STATUS_CATEGORIES)
    out["total_amount"] = _parse_numeric(out["total_amount"], "total_amount")
    return out


def cast_order_items(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["quantity"] = _parse_numeric(out["quantity"], "quantity").astype("int64")
    out["unit_price"] = _parse_numeric(out["unit_price"], "unit_price")
    return out


def cast_payments(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["payment_date"] = _parse_dates(out["payment_date"], "payment_date")
    out["payment_method"] = pd.Categorical(out["payment_method"], categories=PAYMENT_METHOD_CATEGORIES)
    out["payment_status"] = pd.Categorical(out["payment_status"], categories=PAYMENT_STATUS_CATEGORIES)
    out["amount"] = _parse_numeric(out["amount"], "amount")
    return out
