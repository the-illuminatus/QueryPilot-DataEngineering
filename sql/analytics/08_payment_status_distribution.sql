-- Payment status distribution.

SELECT
    payment_status,
    COUNT(*) AS payment_count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_of_payments
FROM payments
GROUP BY payment_status
ORDER BY payment_count DESC;
