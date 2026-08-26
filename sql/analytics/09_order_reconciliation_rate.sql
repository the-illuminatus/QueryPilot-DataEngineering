-- Share of orders whose source total_amount reconciles against the sum
-- of their order_items (the Phase 4 reconciliation flag, carried
-- through unchanged into the warehouse).

SELECT
    COUNT(*) AS total_orders,
    SUM(CASE WHEN total_amount_reconciled THEN 1 ELSE 0 END) AS reconciled_orders,
    SUM(CASE WHEN NOT total_amount_reconciled THEN 1 ELSE 0 END) AS non_reconciled_orders,
    ROUND(
        100.0 * SUM(CASE WHEN total_amount_reconciled THEN 1 ELSE 0 END) / COUNT(*), 2
    ) AS reconciliation_rate_pct
FROM orders;
