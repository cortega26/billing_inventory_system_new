-- Schema for Inventory and Billing System

-- Categories table
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

-- Products table
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    category_id INTEGER,
    cost_price INTEGER NOT NULL DEFAULT 0 CHECK (cost_price >= 0),
    sell_price INTEGER NOT NULL DEFAULT 0 CHECK (sell_price >= 0),
    barcode TEXT UNIQUE,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
);

-- Inventory table
CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL UNIQUE,
    quantity DECIMAL(10,3) NOT NULL DEFAULT 0.000 CHECK (quantity >= 0),
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);

-- Customers table
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    identifier_9 TEXT NOT NULL UNIQUE,
    name TEXT
);

-- Customer identifiers table
CREATE TABLE IF NOT EXISTS customer_identifiers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    identifier_3or4 TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
);

-- Sales table
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER,
    date TEXT NOT NULL,
    total_amount INTEGER NOT NULL DEFAULT 0,
    total_profit INTEGER NOT NULL DEFAULT 0,
    receipt_id TEXT,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE SET NULL
);

-- Sale items table
CREATE TABLE IF NOT EXISTS sale_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity DECIMAL(10,3) NOT NULL,
    price INTEGER NOT NULL,
    profit INTEGER NOT NULL,
    FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
);

-- Purchases table
CREATE TABLE IF NOT EXISTS purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier TEXT NOT NULL,
    date TEXT NOT NULL,
    total_amount INTEGER NOT NULL
);

-- Purchase items table
CREATE TABLE IF NOT EXISTS purchase_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity DECIMAL(10,3) NOT NULL,
    price INTEGER NOT NULL,
    FOREIGN KEY (purchase_id) REFERENCES purchases(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
);

-- Inventory adjustments table
CREATE TABLE IF NOT EXISTS inventory_adjustments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    quantity_change DECIMAL(10,3) NOT NULL,
    reason TEXT NOT NULL,
    date TEXT NOT NULL,
    FOREIGN KEY (product_id) REFERENCES products(id)
);

-- Add composite indexes for frequently joined queries
CREATE INDEX IF NOT EXISTS idx_sale_items_composite ON sale_items(sale_id, product_id);
CREATE INDEX IF NOT EXISTS idx_sales_date_customer ON sales(date, customer_id);

-- Performance Indexes
CREATE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode);
CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);
CREATE INDEX IF NOT EXISTS idx_sale_items_product_id ON sale_items(product_id);
CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(date); 