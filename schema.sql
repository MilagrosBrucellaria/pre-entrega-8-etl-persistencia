CREATE TABLE IF NOT EXISTS customer_sales_summary (
    customer_id TEXT NOT NULL,
    country TEXT NOT NULL,
    invoice_count INTEGER NOT NULL,
    product_count INTEGER NOT NULL,
    total_units INTEGER NOT NULL,
    total_amount REAL NOT NULL,
    first_purchase_date TEXT,
    last_purchase_date TEXT,
    etl_loaded_at TEXT NOT NULL,
    PRIMARY KEY (customer_id, country)
);