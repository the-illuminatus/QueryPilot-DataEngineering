-- Revenue by product category, based on order line items. Cancelled and
-- returned orders are excluded since they did not result in kept
-- revenue.

SELECT
    p.category,
    SUM(oi.line_total) AS revenue,
    COUNT(DISTINCT oi.order_id) AS order_count
FROM order_items oi
JOIN products p ON p.product_id = oi.product_id
JOIN orders o ON o.order_id = oi.order_id
WHERE o.status NOT IN ('CANCELLED', 'RETURNED')
GROUP BY p.category
ORDER BY revenue DESC;
