-- =============================================================================
-- 00_database_setup.sql
-- E-Commerce Customer Retention & Revenue Intelligence (Olist dataset)
--
-- Creates the `raw` schema and one landing table per source CSV.
-- Raw tables mirror the source files exactly: no constraints are enforced at
-- this stage so that data-quality issues are preserved for inspection.
-- Analytical (typed/cleaned) objects are created separately in the
-- `staging` and `analytics` schemas by later scripts.
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS analytics;

-- ---------------------------------------------------------------------------
-- raw.customers  (source: olist_customers_dataset.csv)
-- Grain: one row per customer_id (order-level customer record).
-- IMPORTANT: customer_id is unique per *order*, not per person.
--            customer_unique_id identifies the same person across orders.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS raw.customers CASCADE;
CREATE TABLE raw.customers (
    customer_id              TEXT PRIMARY KEY,
    customer_unique_id       TEXT NOT NULL,
    customer_zip_code_prefix TEXT,
    customer_city            TEXT,
    customer_state           TEXT
);

-- ---------------------------------------------------------------------------
-- raw.orders  (source: olist_orders_dataset.csv)
-- Grain: one row per order_id.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS raw.orders CASCADE;
CREATE TABLE raw.orders (
    order_id                      TEXT PRIMARY KEY,
    customer_id                   TEXT NOT NULL,
    order_status                  TEXT NOT NULL,
    order_purchase_timestamp      TIMESTAMP,
    order_approved_at             TIMESTAMP,
    order_delivered_carrier_date  TIMESTAMP,
    order_delivered_customer_date TIMESTAMP,
    order_estimated_delivery_date TIMESTAMP
);

-- ---------------------------------------------------------------------------
-- raw.order_items  (source: olist_order_items_dataset.csv)
-- Grain: one row per (order_id, order_item_id) - an item line within an order.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS raw.order_items CASCADE;
CREATE TABLE raw.order_items (
    order_id            TEXT NOT NULL,
    order_item_id       INTEGER NOT NULL,
    product_id          TEXT,
    seller_id           TEXT,
    shipping_limit_date TIMESTAMP,
    price               NUMERIC(12,2),
    freight_value       NUMERIC(12,2),
    PRIMARY KEY (order_id, order_item_id)
);

-- ---------------------------------------------------------------------------
-- raw.order_payments  (source: olist_order_payments_dataset.csv)
-- Grain: one row per (order_id, payment_sequential) - an order may be paid
-- with several payment records (e.g. voucher + credit card).
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS raw.order_payments CASCADE;
CREATE TABLE raw.order_payments (
    order_id             TEXT NOT NULL,
    payment_sequential   INTEGER NOT NULL,
    payment_type         TEXT,
    payment_installments INTEGER,
    payment_value        NUMERIC(12,2),
    PRIMARY KEY (order_id, payment_sequential)
);

-- ---------------------------------------------------------------------------
-- raw.order_reviews  (source: olist_order_reviews_dataset.csv)
-- Grain: one row per review record. NOTE: review_id is NOT unique in the
-- source file (a small number of review_ids are attached to more than one
-- order) so no primary key is declared; referential checks live in
-- 01_data_quality_checks.sql.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS raw.order_reviews CASCADE;
CREATE TABLE raw.order_reviews (
    review_id              TEXT,
    order_id               TEXT,
    review_score           INTEGER,
    review_comment_title   TEXT,
    review_comment_message TEXT,
    review_creation_date   TIMESTAMP,
    review_answer_timestamp TIMESTAMP
);

-- ---------------------------------------------------------------------------
-- raw.products  (source: olist_products_dataset.csv)
-- Grain: one row per product_id.
-- Column names kept as in the source file (including source typos such as
-- product_name_lenght) so raw faithfully mirrors the dataset.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS raw.products CASCADE;
CREATE TABLE raw.products (
    product_id                 TEXT PRIMARY KEY,
    product_category_name      TEXT,
    product_name_lenght        INTEGER,
    product_description_lenght INTEGER,
    product_photos_qty         INTEGER,
    product_weight_g           INTEGER,
    product_length_cm          INTEGER,
    product_height_cm          INTEGER,
    product_width_cm           INTEGER
);

-- ---------------------------------------------------------------------------
-- raw.sellers  (source: olist_sellers_dataset.csv)
-- Grain: one row per seller_id.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS raw.sellers CASCADE;
CREATE TABLE raw.sellers (
    seller_id              TEXT PRIMARY KEY,
    seller_zip_code_prefix TEXT,
    seller_city            TEXT,
    seller_state           TEXT
);

-- ---------------------------------------------------------------------------
-- raw.geolocation  (source: olist_geolocation_dataset.csv)
-- Grain: one row per (zip prefix, lat, lng) sample point; a zip prefix can
-- legitimately appear many times with different coordinates.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS raw.geolocation CASCADE;
CREATE TABLE raw.geolocation (
    geolocation_zip_code_prefix TEXT,
    geolocation_lat             NUMERIC(10,6),
    geolocation_lng             NUMERIC(10,6),
    geolocation_city            TEXT,
    geolocation_state           TEXT
);

-- ---------------------------------------------------------------------------
-- raw.category_translation  (source: product_category_name_translation.csv)
-- Grain: one row per Portuguese category name -> English translation.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS raw.category_translation CASCADE;
CREATE TABLE raw.category_translation (
    product_category_name         TEXT PRIMARY KEY,
    product_category_name_english TEXT
);
