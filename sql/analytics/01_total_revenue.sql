-- Total revenue: sum of successfully collected payments. Deliberately
-- based on payments.amount (money actually received), not orders.total,
-- since an order can exist without a successful payment behind it.

SELECT
    SUM(amount) AS total_revenue
FROM payments
WHERE payment_status = 'SUCCESS';
