-- Sample SQL: Nested / subquery patterns for lineage extraction

-- 1. Subquery in WHERE: High-value customers only
SELECT
    customer_id,
    customer_name,
    email
FROM customers
WHERE customer_id IN (
    SELECT customer_id
    FROM orders
    WHERE total_amount > 500
);


-- 2. Derived table in FROM: Top products per category
SELECT
    ranked.category_name,
    ranked.product_name,
    ranked.total_revenue
FROM (
    SELECT
        cat.category_name,
        p.product_name,
        SUM(oi.quantity * oi.unit_price) AS total_revenue,
        ROW_NUMBER() OVER (
            PARTITION BY cat.category_id
            ORDER BY SUM(oi.quantity * oi.unit_price) DESC
        ) AS rnk
    FROM order_items oi
    INNER JOIN products p   ON oi.product_id  = p.product_id
    INNER JOIN categories cat ON p.category_id = cat.category_id
    GROUP BY cat.category_id, cat.category_name, p.product_id, p.product_name
) ranked
WHERE ranked.rnk = 1;


-- 3. CTE: Monthly revenue with running total
WITH monthly_revenue AS (
    SELECT
        DATE_TRUNC('month', order_date) AS month,
        SUM(total_amount)               AS revenue
    FROM orders
    GROUP BY DATE_TRUNC('month', order_date)
)
SELECT
    month,
    revenue,
    SUM(revenue) OVER (ORDER BY month) AS running_total
FROM monthly_revenue
ORDER BY month;


-- 4. Correlated subquery: Latest order date per customer
SELECT
    c.customer_id,
    c.customer_name,
    (
        SELECT MAX(o.order_date)
        FROM orders o
        WHERE o.customer_id = c.customer_id
    ) AS last_order_date
FROM customers c;


-- 5. INSERT from nested CTE: Populate churn risk table
WITH last_activity AS (
    SELECT
        customer_id,
        MAX(order_date) AS last_order_date
    FROM orders
    GROUP BY customer_id
),
inactive AS (
    SELECT
        la.customer_id,
        la.last_order_date,
        CURRENT_DATE - la.last_order_date AS days_inactive
    FROM last_activity la
    WHERE CURRENT_DATE - la.last_order_date > 90
)
INSERT INTO churn_risk_customers
SELECT
    c.customer_id,
    c.customer_name,
    c.email,
    i.last_order_date,
    i.days_inactive
FROM inactive i
INNER JOIN customers c ON i.customer_id = c.customer_id;


-- 6. Scalar subquery in SELECT: Enrich rows with aggregated context
SELECT
    p.product_id,
    p.product_name,
    p.price,
    (
        SELECT AVG(price)
        FROM products
        WHERE category_id = p.category_id
    ) AS category_avg_price,
    p.price - (
        SELECT AVG(price)
        FROM products
        WHERE category_id = p.category_id
    ) AS price_vs_category_avg
FROM products p;
