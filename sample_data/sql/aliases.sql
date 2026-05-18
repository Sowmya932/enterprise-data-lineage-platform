-- Sample SQL: Alias patterns for lineage extraction

-- 1. Column aliases — scalar expressions
SELECT
    customer_id                          AS cust_id,
    first_name || ' ' || last_name       AS full_name,
    LOWER(email)                         AS email_normalized,
    EXTRACT(YEAR FROM created_at)        AS signup_year
FROM customers;


-- 2. Table aliases — multi-source query
SELECT
    ord.order_id       AS id,
    ord.order_date     AS placed_on,
    cust.customer_name AS buyer,
    cust.region        AS buyer_region
FROM orders   ord
INNER JOIN customers cust ON ord.customer_id = cust.customer_id;


-- 3. Alias reuse in ORDER BY / GROUP BY
SELECT
    DATE_TRUNC('week', o.order_date) AS week_start,
    c.region                         AS sales_region,
    SUM(o.total_amount)              AS weekly_revenue
FROM orders o
INNER JOIN customers c ON o.customer_id = c.customer_id
GROUP BY week_start, sales_region
ORDER BY week_start, weekly_revenue DESC;


-- 4. CTE with aliases flowing into outer query
WITH customer_stats AS (
    SELECT
        customer_id                   AS cust_id,
        COUNT(order_id)               AS order_count,
        SUM(total_amount)             AS lifetime_value,
        MAX(order_date)               AS last_order
    FROM orders
    GROUP BY customer_id
)
SELECT
    c.customer_name   AS name,
    c.email           AS contact,
    cs.order_count,
    cs.lifetime_value AS ltv,
    cs.last_order
FROM customer_stats cs
INNER JOIN customers c ON cs.cust_id = c.customer_id;


-- 5. INSERT with aliased subquery columns
INSERT INTO sales_rep_leaderboard
SELECT
    e.employee_id   AS rep_id,
    e.full_name     AS rep_name,
    SUM(s.amount)   AS total_sold,
    COUNT(s.sale_id)AS deal_count,
    AVG(s.amount)   AS avg_deal_size
FROM sales s
INNER JOIN employees e ON s.employee_id = e.employee_id
GROUP BY e.employee_id, e.full_name
ORDER BY total_sold DESC;
