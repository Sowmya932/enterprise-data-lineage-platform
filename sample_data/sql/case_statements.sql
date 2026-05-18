-- Sample SQL: CASE WHEN statements for lineage extraction

-- 1. Simple value mapping — order status label
SELECT
    order_id,
    order_date,
    total_amount,
    CASE status
        WHEN 'P' THEN 'pending'
        WHEN 'C' THEN 'confirmed'
        WHEN 'S' THEN 'shipped'
        WHEN 'D' THEN 'delivered'
        WHEN 'X' THEN 'cancelled'
        ELSE 'unknown'
    END AS order_status_label
FROM orders;


-- 2. Searched CASE — customer tier classification
SELECT
    customer_id,
    customer_name,
    lifetime_value,
    CASE
        WHEN lifetime_value >= 10000 THEN 'platinum'
        WHEN lifetime_value >= 5000  THEN 'gold'
        WHEN lifetime_value >= 1000  THEN 'silver'
        ELSE                              'bronze'
    END AS customer_tier
FROM customer_summary;


-- 3. CASE inside aggregate — conditional counts
SELECT
    region,
    COUNT(order_id)                                              AS total_orders,
    COUNT(CASE WHEN status = 'delivered' THEN 1 END)            AS delivered,
    COUNT(CASE WHEN status = 'cancelled' THEN 1 END)            AS cancelled,
    SUM(CASE WHEN status = 'delivered' THEN total_amount END)   AS delivered_revenue
FROM orders
INNER JOIN customers ON orders.customer_id = customers.customer_id
GROUP BY region;


-- 4. CASE for bucketing — age-group segmentation
SELECT
    customer_id,
    customer_name,
    date_of_birth,
    CASE
        WHEN EXTRACT(YEAR FROM AGE(date_of_birth)) < 25 THEN 'gen_z'
        WHEN EXTRACT(YEAR FROM AGE(date_of_birth)) < 40 THEN 'millennial'
        WHEN EXTRACT(YEAR FROM AGE(date_of_birth)) < 55 THEN 'gen_x'
        ELSE 'boomer_plus'
    END AS age_group
FROM customers;


-- 5. Nested CASE — multi-dimension risk flag
SELECT
    e.employee_id,
    e.department,
    a.login_count,
    a.failed_logins,
    CASE
        WHEN a.failed_logins > 10 THEN
            CASE
                WHEN a.login_count < 5 THEN 'critical'
                ELSE 'high'
            END
        WHEN a.failed_logins > 3 THEN 'medium'
        ELSE 'low'
    END AS risk_level
FROM employees e
INNER JOIN access_logs a ON e.employee_id = a.employee_id;


-- 6. INSERT with CASE — populate flag table
INSERT INTO order_flags
SELECT
    order_id,
    customer_id,
    total_amount,
    CASE
        WHEN total_amount > 1000 AND status != 'cancelled' THEN TRUE
        ELSE FALSE
    END AS is_high_value,
    CASE
        WHEN order_date < CURRENT_DATE - INTERVAL '30 days'
             AND status NOT IN ('delivered', 'cancelled') THEN TRUE
        ELSE FALSE
    END AS is_overdue
FROM orders;
