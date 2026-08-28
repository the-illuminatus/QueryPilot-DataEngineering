-- Most recent activity dates in the current warehouse state. Used only
-- for the dashboard's "data as of" line -- the dataset is synthetic and
-- generated with recent timestamps, not a live feed.

SELECT
    (SELECT MAX(order_date) FROM orders) AS latest_order_date,
    (SELECT MAX(payment_date) FROM payments) AS latest_payment_date;
