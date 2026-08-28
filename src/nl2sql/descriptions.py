"""Known table descriptions: short, factual domain notes that ground the
NL2SQL layer in what the warehouse actually models (an India-focused
payments/e-commerce dataset, all money in INR). They restate the DDL
header comments in sql/ddl/*.sql plus the dataset's documented domain
(README.md) -- nothing here contradicts the schema or the DDL. Kept as a
small static mapping rather than parsed out of the DDL files at runtime,
since these are prose, not structured metadata.

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
    "customers": (
        "Customer dimension table for an India-focused e-commerce business. "
        "city and state are the customer's location in India (state is an "
        "Indian state or union territory)."
    ),
    "products": (
        "Product dimension table for an Indian online marketplace. category "
        "is the marketplace department; price is the list price in Indian "
        "rupees (INR)."
    ),
    "orders": (
        "Order fact table. All monetary amounts are in Indian rupees (INR). "
        "source_total_amount, calculated_total_amount, "
        "total_amount_difference, and total_amount_reconciled are order "
        "reconciliation fields: the source value is never overwritten by "
        "the calculated one."
    ),
    "order_items": (
        "Line items belonging to an order, linking orders to products. "
        "unit_price and line_total are in Indian rupees (INR)."
    ),
    "payments": (
        "Payments recorded against an order, amount in Indian rupees (INR). "
        "payment_method includes UPI, NET_BANKING, WALLET and COD alongside "
        "cards, reflecting how Indian customers pay."
    ),
}
