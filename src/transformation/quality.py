"""Post-transform / post-write quality checks.

Verifies exactly what Phase 4 asks for: the transformed schema has the
right dtypes, no unexpected nulls were introduced, the derived
calculations (line_total, reconciliation flag) are internally consistent,
and the Parquet file actually written matches what was transformed --
file exists, row count matches, expected columns and dtypes are present.

Every check here indicates a pipeline bug if it fails, never a business
data condition -- a reconciliation *mismatch* is a legitimate, expected
outcome handled elsewhere (the transformation report), not a failure of
these checks.
"""

from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

EXPECTED_SCHEMA = {
    "customers": {
        "customer_id": "object",
        "full_name": "object",
        "email": "object",
        "city": "object",
        "country": "object",
        "signup_date": "datetime64[ns]",
    },
    "products": {
        "product_id": "object",
        "product_name": "object",
        "category": "object",
        "price": "float64",
    },
    "orders": {
        "order_id": "object",
        "customer_id": "object",
        "order_date": "datetime64[ns]",
        "status": "category",
        "source_total_amount": "float64",
        "calculated_total_amount": "float64",
        "total_amount_difference": "float64",
        "total_amount_reconciled": "bool",
    },
    "order_items": {
        "order_item_id": "object",
        "order_id": "object",
        "product_id": "object",
        "quantity": "int64",
        "unit_price": "float64",
        "line_total": "float64",
    },
    "payments": {
        "payment_id": "object",
        "order_id": "object",
        "payment_date": "datetime64[ns]",
        "payment_method": "category",
        "payment_status": "category",
        "amount": "float64",
    },
}

REQUIRED_NON_NULL_COLUMNS = {
    "customers": ["customer_id", "full_name", "email", "city", "country", "signup_date"],
    "products": ["product_id", "product_name", "category", "price"],
    "orders": ["order_id", "customer_id", "order_date", "status", "source_total_amount"],
    "order_items": ["order_item_id", "order_id", "product_id", "quantity", "unit_price", "line_total"],
    "payments": ["payment_id", "order_id", "payment_date", "payment_method", "payment_status", "amount"],
}


class ParquetQualityError(Exception):
    """Raised when transformed data or a written Parquet file fails a
    structural or completeness check."""


def verify_dtypes(df: pd.DataFrame, entity: str) -> None:
    expected = EXPECTED_SCHEMA[entity]
    mismatches = []
    for column, expected_dtype in expected.items():
        if column not in df.columns:
            mismatches.append(f"missing column '{column}'")
            continue
        actual_dtype = str(df[column].dtype)
        if actual_dtype != expected_dtype:
            mismatches.append(f"'{column}' expected {expected_dtype}, got {actual_dtype}")
    if mismatches:
        raise ParquetQualityError(f"{entity}: schema mismatch: {'; '.join(mismatches)}")


def verify_no_unexpected_nulls(df: pd.DataFrame, entity: str) -> None:
    for column in REQUIRED_NON_NULL_COLUMNS[entity]:
        null_count = int(df[column].isna().sum())
        if null_count:
            raise ParquetQualityError(
                f"{entity}: {null_count} unexpected null(s) in required column '{column}'"
            )


def verify_line_totals(order_items_df: pd.DataFrame) -> None:
    expected = (order_items_df["quantity"] * order_items_df["unit_price"]).round(2)
    mismatches = (order_items_df["line_total"] - expected).abs() > 0.01
    if mismatches.any():
        raise ParquetQualityError(
            f"order_items: {int(mismatches.sum())} row(s) have a line_total inconsistent "
            f"with quantity * unit_price"
        )


def verify_order_reconciliation_consistency(orders_df: pd.DataFrame) -> None:
    expected_flag = orders_df["total_amount_difference"].abs() <= 0.01
    mismatches = expected_flag != orders_df["total_amount_reconciled"]
    if mismatches.any():
        raise ParquetQualityError(
            f"orders: {int(mismatches.sum())} row(s) have a total_amount_reconciled flag "
            f"inconsistent with total_amount_difference"
        )


def verify_parquet_file(entity: str, path: Path, expected_row_count: int) -> None:
    if not path.exists():
        raise ParquetQualityError(f"{entity}: expected Parquet file not found at {path}")

    parquet_file = pq.ParquetFile(path)
    actual_row_count = parquet_file.metadata.num_rows
    if actual_row_count != expected_row_count:
        raise ParquetQualityError(
            f"{entity}: row count mismatch -- expected {expected_row_count}, "
            f"Parquet file has {actual_row_count}"
        )

    expected_columns = set(EXPECTED_SCHEMA[entity].keys())
    actual_columns = set(parquet_file.schema_arrow.names)
    missing_columns = expected_columns - actual_columns
    if missing_columns:
        raise ParquetQualityError(f"{entity}: Parquet file is missing column(s) {missing_columns}")
