"""Known table descriptions, sourced directly from the header comments in
sql/ddl/*.sql -- not invented. Kept as a small static mapping rather than
parsed out of the DDL files at runtime, since these comments are prose,
not structured metadata, and the DDL files are the source of truth for
anyone who wants to verify a description against its origin.

A table with no entry here (e.g. one added to the warehouse later,
without an accompanying description) simply gets no description in the
generated context -- discovery.py must never fail or guess one.
"""

TABLE_DESCRIPTIONS = {
    "pipeline_batches": (
        "Batch lineage / load ledger. One row per warehouse load attempt. "
        "Only SUCCESS or FAILED are ever durably observable -- IN_PROGRESS "
        "is set and cleared within the same load transaction. Never "
        "truncated or overwritten wholesale; it is the permanent history "
        "of every batch ever loaded, independent of the current-state "
        "entity tables below."
    ),
    "customers": "Customer dimension table.",
    "products": "Product dimension table, including category and price.",
    "orders": (
        "Order fact table. source_total_amount, calculated_total_amount, "
        "total_amount_difference, and total_amount_reconciled are order "
        "reconciliation fields: the source value is never overwritten by "
        "the calculated one."
    ),
    "order_items": "Line items belonging to an order, linking orders to products.",
    "payments": "Payments recorded against an order.",
}
