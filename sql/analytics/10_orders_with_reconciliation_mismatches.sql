-- Orders whose source total_amount does not reconcile against the sum
-- of their order_items, largest discrepancy first. A concrete,
-- investigable list for whoever owns data quality follow-up.

SELECT
    order_id,
    customer_id,
    order_date,
    source_total_amount,
    calculated_total_amount,
    total_amount_difference
FROM orders
WHERE NOT total_amount_reconciled
ORDER BY ABS(total_amount_difference) DESC;
