-- Revenue by calendar month, based on successful payments.

SELECT
    DATE_TRUNC('month', payment_date)::DATE AS month,
    SUM(amount) AS revenue,
    COUNT(*) AS successful_payments
FROM payments
WHERE payment_status = 'SUCCESS'
GROUP BY 1
ORDER BY 1;
