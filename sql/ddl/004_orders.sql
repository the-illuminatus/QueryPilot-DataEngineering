-- source_total_amount/calculated_total_amount/total_amount_difference/
-- total_amount_reconciled are the Phase 4 order-reconciliation fields,
-- carried through unchanged: the source value is never overwritten.

CREATE TABLE IF NOT EXISTS orders (
    order_id VARCHAR(20) PRIMARY KEY,
    customer_id VARCHAR(20) NOT NULL REFERENCES customers(customer_id),
    order_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL
        CHECK (status IN ('PLACED', 'SHIPPED', 'DELIVERED', 'CANCELLED', 'RETURNED')),
    source_total_amount NUMERIC(12, 2) NOT NULL CHECK (source_total_amount >= 0),
    calculated_total_amount NUMERIC(12, 2) NOT NULL CHECK (calculated_total_amount >= 0),
    total_amount_difference NUMERIC(12, 2) NOT NULL,
    total_amount_reconciled BOOLEAN NOT NULL,
    batch_id VARCHAR(64) NOT NULL REFERENCES pipeline_batches(batch_id)
);
