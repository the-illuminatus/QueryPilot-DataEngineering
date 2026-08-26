CREATE TABLE IF NOT EXISTS payments (
    payment_id VARCHAR(20) PRIMARY KEY,
    order_id VARCHAR(20) NOT NULL REFERENCES orders(order_id),
    payment_date DATE NOT NULL,
    payment_method VARCHAR(20) NOT NULL
        CHECK (payment_method IN ('CREDIT_CARD', 'DEBIT_CARD', 'UPI', 'NET_BANKING', 'WALLET', 'COD')),
    payment_status VARCHAR(20) NOT NULL
        CHECK (payment_status IN ('SUCCESS', 'FAILED', 'PENDING', 'REFUNDED')),
    amount NUMERIC(12, 2) NOT NULL CHECK (amount >= 0),
    batch_id VARCHAR(64) NOT NULL REFERENCES pipeline_batches(batch_id)
);
