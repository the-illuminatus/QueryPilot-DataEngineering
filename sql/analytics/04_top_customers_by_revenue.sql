-- Top 10 customers by successfully collected revenue.

SELECT
    c.customer_id,
    c.full_name,
    c.city,
    c.state,
    SUM(pay.amount) AS revenue,
    COUNT(DISTINCT pay.payment_id) AS successful_payments
FROM payments pay
JOIN orders o ON o.order_id = pay.order_id
JOIN customers c ON c.customer_id = o.customer_id
WHERE pay.payment_status = 'SUCCESS'
GROUP BY c.customer_id, c.full_name, c.city, c.state
ORDER BY revenue DESC
LIMIT 10;
