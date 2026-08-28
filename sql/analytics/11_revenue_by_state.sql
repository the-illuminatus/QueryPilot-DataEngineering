-- Revenue by customer state, based on successfully collected payments.
-- Attributes each successful payment to the home state of the customer
-- who placed the underlying order -- a geographic view of where
-- collected INR revenue comes from.

SELECT
    c.state,
    SUM(pay.amount) AS revenue,
    COUNT(DISTINCT o.customer_id) AS paying_customers,
    COUNT(DISTINCT pay.payment_id) AS successful_payments
FROM payments pay
JOIN orders o ON o.order_id = pay.order_id
JOIN customers c ON c.customer_id = o.customer_id
WHERE pay.payment_status = 'SUCCESS'
GROUP BY c.state
ORDER BY revenue DESC;
