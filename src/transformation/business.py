"""Business transformations: derived and reconciliation fields.

Implements exactly what Phase 4 asks for -- order_items.line_total, and an
orders-level reconciliation between the source total_amount and the total
actually implied by its order_items. The source value is never
overwritten; the comparison is made observable through dedicated derived
columns instead. Nothing beyond that is added here -- the analytical
model itself belongs to Phase 5.
"""

import pandas as pd

RECONCILIATION_TOLERANCE = 0.01  # cents-level rounding tolerance


def add_line_total(order_items_df: pd.DataFrame) -> pd.DataFrame:
    out = order_items_df.copy()
    out["line_total"] = (out["quantity"] * out["unit_price"]).round(2)
    return out


def reconcile_order_totals(orders_df: pd.DataFrame, order_items_df: pd.DataFrame) -> pd.DataFrame:
    calculated = (
        order_items_df.groupby("order_id")["line_total"].sum().rename("calculated_total_amount")
    )

    out = orders_df.rename(columns={"total_amount": "source_total_amount"}).copy()
    out = out.merge(calculated, on="order_id", how="left")
    out["calculated_total_amount"] = out["calculated_total_amount"].fillna(0.0).round(2)
    out["total_amount_difference"] = (
        out["source_total_amount"] - out["calculated_total_amount"]
    ).round(2)
    out["total_amount_reconciled"] = out["total_amount_difference"].abs() <= RECONCILIATION_TOLERANCE
    return out
