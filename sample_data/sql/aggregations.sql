-- Sample SQL: Aggregation queries for lineage extraction

-- 1. Total sales per customer
SELECT
    customer_id,
    COUNT(order_id)   AS total_orders,
    SUM(total_amount) AS total_spent,
    AVG(total_amount) AS avg_order_value
FROM orders
GROUP BY customer_id;


-- 2. Monthly revenue summary
SELECT
    DATE_TRUNC('month', sale_date) AS month,
    SUM(amount)                    AS monthly_revenue,
    COUNT(DISTINCT customer_id)    AS unique_customers
FROM sales
GROUP BY DATE_TRUNC('month', sale_date)
ORDER BY month;


-- 3. INSERT aggregated data into summary table
INSERT INTO monthly_sales_summary
SELECT
    DATE_TRUNC('month', o.order_date) AS month,
    c.region,
    SUM(o.total_amount)               AS total_revenue,
    COUNT(o.order_id)                 AS order_count,
    AVG(o.total_amount)               AS avg_order_value
FROM orders o
INNER JOIN customers c ON o.customer_id = c.customer_id
GROUP BY DATE_TRUNC('month', o.order_date), c.region;


-- 4. Product performance aggregation
INSERT INTO product_performance_summary
SELECT
    p.product_id,
    p.product_name,
    cat.category_name,
    SUM(oi.quantity)               AS total_units_sold,
    SUM(oi.quantity * oi.unit_price) AS total_revenue,
    COUNT(DISTINCT o.customer_id)  AS unique_buyers
FROM order_items oi
INNER JOIN products p ON oi.product_id = p.product_id
INNER JOIN categories cat ON p.category_id = cat.category_id
INNER JOIN orders o ON oi.order_id = o.order_id
GROUP BY p.product_id, p.product_name, cat.category_name;


-- 5. Customer segmentation
INSERT INTO customer_segments
SELECT
    customer_id,
    SUM(total_amount) AS lifetime_value,
    CASE
        WHEN SUM(total_amount) >= 10000 THEN 'platinum'
        WHEN SUM(total_amount) >= 5000  THEN 'gold'
        WHEN SUM(total_amount) >= 1000  THEN 'silver'
        ELSE 'bronze'
    END AS segment
FROM orders
GROUP BY customer_id;
