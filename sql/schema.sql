CREATE TABLE IF NOT EXISTS products (
    stock_code TEXT PRIMARY KEY,
    description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transactions (
    source_row BIGINT PRIMARY KEY,
    invoice_no TEXT NOT NULL,
    stock_code TEXT NOT NULL,
    invoice_date TIMESTAMP NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(14, 4) NOT NULL CHECK (unit_price > 0),
    country TEXT
);

CREATE INDEX IF NOT EXISTS transactions_product_date_idx
    ON transactions (stock_code, invoice_date);

CREATE TABLE IF NOT EXISTS daily_sales (
    stock_code TEXT NOT NULL REFERENCES products(stock_code),
    sales_date DATE NOT NULL,
    quantity BIGINT NOT NULL CHECK (quantity >= 0),
    PRIMARY KEY (stock_code, sales_date)
);
