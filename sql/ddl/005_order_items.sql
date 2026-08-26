CREATE TABLE IF NOT EXISTS order_items (
    order_item_id VARCHAR(20) PRIMARY KEY,
    order_id VARCHAR(20) NOT NULL REFERENCES orders(order_id),
    product_id VARCHAR(20) NOT NULL REFERENCES products(product_id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(12, 2) NOT NULL CHECK (unit_price > 0),
    line_total NUMERIC(12, 2) NOT NULL CHECK (line_total >= 0),
    batch_id VARCHAR(64) NOT NULL REFERENCES pipeline_batches(batch_id)
);
