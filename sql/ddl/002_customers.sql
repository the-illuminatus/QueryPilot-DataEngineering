CREATE TABLE IF NOT EXISTS customers (
    customer_id VARCHAR(20) PRIMARY KEY,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL,
    city TEXT NOT NULL,
    state TEXT NOT NULL,
    signup_date DATE NOT NULL,
    batch_id VARCHAR(64) NOT NULL REFERENCES pipeline_batches(batch_id)
);
