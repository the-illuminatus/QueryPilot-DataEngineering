-- Average order value, using the source (as-recorded) order total.

SELECT
    ROUND(AVG(source_total_amount), 2) AS average_order_value,
    COUNT(*) AS order_count
FROM orders;
