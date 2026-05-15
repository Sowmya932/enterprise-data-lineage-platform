-- Sample SQL: INSERT statements for lineage extraction

-- 1. Simple INSERT INTO ... SELECT (basic lineage)
INSERT INTO sales_summary
SELECT * FROM orders;


-- 2. INSERT with column mapping
INSERT INTO sales_summary (order_id, customer_id, total_amount, order_date)
SELECT order_id, customer_id, total_amount, order_date
FROM orders
WHERE order_date >= '2024-01-01';


-- 3. INSERT from multiple sources via JOIN
INSERT INTO customer_order_summary
SELECT
    c.customer_id,
    c.customer_name,
    COUNT(o.order_id)   AS order_count,
    SUM(o.total_amount) AS total_spent
FROM customers c
LEFT JOIN orders o ON c.customer_id = o.customer_id
GROUP BY c.customer_id, c.customer_name;


-- 4. INSERT with subquery
INSERT INTO high_value_customers
SELECT customer_id, customer_name, email
FROM customers
WHERE customer_id IN (
    SELECT customer_id
    FROM orders
    GROUP BY customer_id
    HAVING SUM(total_amount) > 5000
);


-- 5. INSERT into audit/log table
INSERT INTO lineage_audit_log (table_name, operation, row_count, executed_at)
SELECT
    'sales_summary'     AS table_name,
    'INSERT'            AS operation,
    COUNT(*)            AS row_count,
    NOW()               AS executed_at
FROM orders;


-- 6. CREATE TABLE AS SELECT (CTAS)
CREATE TABLE regional_sales_summary AS
SELECT
    c.region,
    DATE_TRUNC('month', o.order_date) AS month,
    SUM(o.total_amount)               AS total_revenue,
    COUNT(o.order_id)                 AS order_count
FROM orders o
INNER JOIN customers c ON o.customer_id = c.customer_id
GROUP BY c.region, DATE_TRUNC('month', o.order_date);
