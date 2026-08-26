-- Payment method distribution.

SELECT
    payment_method,
    COUNT(*) AS payment_count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_of_payments
FROM payments
GROUP BY payment_method
ORDER BY payment_count DESC;
