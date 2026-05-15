-- Sample SQL: JOIN queries for lineage extraction

-- 1. INNER JOIN: Orders with customer info
SELECT
    o.order_id,
    o.order_date,
    c.customer_name,
    c.email
FROM orders o
INNER JOIN customers c ON o.customer_id = c.customer_id;


-- 2. LEFT JOIN: Orders with optional payment details
SELECT
    o.order_id,
    o.total_amount,
    p.payment_method,
    p.payment_status
FROM orders o
LEFT JOIN payments p ON o.order_id = p.order_id;


-- 3. Multi-table JOIN: Sales report with product and category
SELECT
    s.sale_id,
    s.sale_date,
    p.product_name,
    p.price,
    cat.category_name,
    c.customer_name
FROM sales s
INNER JOIN products p ON s.product_id = p.product_id
INNER JOIN categories cat ON p.category_id = cat.category_id
INNER JOIN customers c ON s.customer_id = c.customer_id;


-- 4. INSERT with JOIN: Populate denormalized reporting table
INSERT INTO order_details_report
SELECT
    o.order_id,
    o.order_date,
    c.customer_name,
    c.region,
    p.product_name,
    oi.quantity,
    oi.unit_price
FROM orders o
INNER JOIN customers c ON o.customer_id = c.customer_id
INNER JOIN order_items oi ON o.order_id = oi.order_id
INNER JOIN products p ON oi.product_id = p.product_id;
