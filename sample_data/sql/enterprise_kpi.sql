-- =============================================================================
-- Enterprise KPI, Reporting & Finance SQL Samples
-- =============================================================================
-- These statements are designed to be submitted to POST /column/parse-sql.
-- Each statement covers a distinct transformation pattern so the column lineage
-- graph captures all supported transformation_type values.
--
-- transformation_type legend
-- --------------------------
--   DIRECT         – plain copy / pass-through
--   ALIAS          – renamed via AS (no computation)
--   AGGREGATE_SUM  – SUM(...)
--   AGGREGATE_COUNT– COUNT(...)
--   AGGREGATE_AVG  – AVG(...)
--   AGGREGATE_MAX  – MAX(...)
--   AGGREGATE_MIN  – MIN(...)
--   CASE_WHEN      – CASE WHEN … END
--   DERIVED        – mixed / other computation
-- =============================================================================


-- ---------------------------------------------------------------------------
-- 1. Daily Revenue KPI
--    source: orders  →  target: daily_revenue_kpi
--    Types: AGGREGATE_SUM, AGGREGATE_COUNT, ALIAS, DIRECT
-- ---------------------------------------------------------------------------
INSERT INTO daily_revenue_kpi (
    report_date,
    total_revenue,
    order_count,
    avg_order_value,
    max_order_value,
    min_order_value
)
SELECT
    order_date                          AS report_date,       -- ALIAS
    SUM(amount)                         AS total_revenue,     -- AGGREGATE_SUM
    COUNT(id)                           AS order_count,       -- AGGREGATE_COUNT
    AVG(amount)                         AS avg_order_value,   -- AGGREGATE_AVG
    MAX(amount)                         AS max_order_value,   -- AGGREGATE_MAX
    MIN(amount)                         AS min_order_value    -- AGGREGATE_MIN
FROM orders
GROUP BY order_date;


-- ---------------------------------------------------------------------------
-- 2. Customer Lifetime Value (CLV) Calculation
--    sources: orders, customers  →  target: customer_ltv
--    Types: ALIAS, AGGREGATE_SUM, AGGREGATE_COUNT, AGGREGATE_AVG, DERIVED
-- ---------------------------------------------------------------------------
INSERT INTO customer_ltv (
    customer_id,
    customer_name,
    email,
    total_spend,
    total_orders,
    avg_order_value,
    clv_score
)
SELECT
    c.id                                AS customer_id,       -- ALIAS
    c.name                              AS customer_name,     -- ALIAS
    c.email                             AS email,             -- DIRECT
    SUM(o.amount)                       AS total_spend,       -- AGGREGATE_SUM
    COUNT(o.id)                         AS total_orders,      -- AGGREGATE_COUNT
    AVG(o.amount)                       AS avg_order_value,   -- AGGREGATE_AVG
    SUM(o.amount) * 0.1 + COUNT(o.id)  AS clv_score          -- DERIVED
FROM customers c
JOIN orders o ON c.id = o.customer_id
GROUP BY c.id, c.name, c.email;


-- ---------------------------------------------------------------------------
-- 3. Customer Tier Segmentation (CASE WHEN)
--    source: customer_ltv  →  target: customer_segments
--    Types: DIRECT, ALIAS, CASE_WHEN
-- ---------------------------------------------------------------------------
INSERT INTO customer_segments (
    customer_id,
    customer_name,
    total_spend,
    segment,
    discount_rate
)
SELECT
    customer_id,                                               -- DIRECT
    customer_name                       AS name,              -- ALIAS
    total_spend,                                              -- DIRECT
    CASE
        WHEN total_spend >= 10000 THEN 'PLATINUM'
        WHEN total_spend >= 5000  THEN 'GOLD'
        WHEN total_spend >= 1000  THEN 'SILVER'
        ELSE 'BRONZE'
    END                                 AS segment,           -- CASE_WHEN
    CASE
        WHEN total_spend >= 10000 THEN 0.20
        WHEN total_spend >= 5000  THEN 0.15
        WHEN total_spend >= 1000  THEN 0.10
        ELSE 0.05
    END                                 AS discount_rate      -- CASE_WHEN
FROM customer_ltv;


-- ---------------------------------------------------------------------------
-- 4. Monthly Finance Aggregations
--    sources: orders, order_items  →  target: monthly_finance_summary
--    Types: ALIAS, AGGREGATE_SUM, AGGREGATE_COUNT, AGGREGATE_AVG, DERIVED
-- ---------------------------------------------------------------------------
INSERT INTO monthly_finance_summary (
    month,
    year,
    gross_revenue,
    total_units_sold,
    avg_unit_price,
    total_discounts,
    net_revenue
)
SELECT
    DATE_TRUNC('month', o.order_date)   AS month,            -- ALIAS
    EXTRACT(YEAR FROM o.order_date)     AS year,             -- DERIVED
    SUM(o.amount)                       AS gross_revenue,    -- AGGREGATE_SUM
    SUM(oi.quantity)                    AS total_units_sold, -- AGGREGATE_SUM
    AVG(oi.unit_price)                  AS avg_unit_price,   -- AGGREGATE_AVG
    SUM(o.discount_amount)              AS total_discounts,  -- AGGREGATE_SUM
    SUM(o.amount) - SUM(o.discount_amount) AS net_revenue    -- DERIVED
FROM orders o
JOIN order_items oi ON o.id = oi.order_id
GROUP BY DATE_TRUNC('month', o.order_date), EXTRACT(YEAR FROM o.order_date);


-- ---------------------------------------------------------------------------
-- 5. Product Performance Dashboard
--    sources: order_items, products  →  target: product_performance
--    Types: DIRECT, ALIAS, AGGREGATE_SUM, AGGREGATE_COUNT, AGGREGATE_AVG,
--           AGGREGATE_MAX, CASE_WHEN, DERIVED
-- ---------------------------------------------------------------------------
INSERT INTO product_performance (
    product_id,
    product_name,
    category,
    units_sold,
    revenue,
    avg_selling_price,
    max_selling_price,
    return_rate,
    performance_tier
)
SELECT
    p.id                                AS product_id,        -- ALIAS
    p.name                              AS product_name,      -- ALIAS
    p.category,                                               -- DIRECT
    SUM(oi.quantity)                    AS units_sold,        -- AGGREGATE_SUM
    SUM(oi.quantity * oi.unit_price)    AS revenue,           -- DERIVED
    AVG(oi.unit_price)                  AS avg_selling_price, -- AGGREGATE_AVG
    MAX(oi.unit_price)                  AS max_selling_price, -- AGGREGATE_MAX
    CAST(SUM(oi.returned_qty) AS FLOAT)
        / NULLIF(SUM(oi.quantity), 0)   AS return_rate,       -- DERIVED
    CASE
        WHEN SUM(oi.quantity * oi.unit_price) >= 100000 THEN 'TOP'
        WHEN SUM(oi.quantity * oi.unit_price) >= 10000  THEN 'MID'
        ELSE 'TAIL'
    END                                 AS performance_tier   -- CASE_WHEN
FROM order_items oi
JOIN products p ON oi.product_id = p.id
GROUP BY p.id, p.name, p.category;


-- ---------------------------------------------------------------------------
-- 6. Sales Rep Commission Report
--    sources: orders, sales_reps  →  target: rep_commission_report
--    Types: DIRECT, ALIAS, AGGREGATE_SUM, AGGREGATE_COUNT, CASE_WHEN, DERIVED
-- ---------------------------------------------------------------------------
INSERT INTO rep_commission_report (
    rep_id,
    rep_name,
    region,
    total_sales,
    closed_deals,
    commission_pct,
    commission_earned,
    quota_status
)
SELECT
    sr.id                               AS rep_id,            -- ALIAS
    sr.full_name                        AS rep_name,          -- ALIAS
    sr.region,                                                -- DIRECT
    SUM(o.amount)                       AS total_sales,       -- AGGREGATE_SUM
    COUNT(o.id)                         AS closed_deals,      -- AGGREGATE_COUNT
    CASE
        WHEN SUM(o.amount) >= 500000 THEN 0.12
        WHEN SUM(o.amount) >= 200000 THEN 0.09
        ELSE 0.06
    END                                 AS commission_pct,    -- CASE_WHEN
    SUM(o.amount) * CASE
        WHEN SUM(o.amount) >= 500000 THEN 0.12
        WHEN SUM(o.amount) >= 200000 THEN 0.09
        ELSE 0.06
    END                                 AS commission_earned, -- DERIVED
    CASE
        WHEN SUM(o.amount) >= sr.quota THEN 'MET'
        ELSE 'MISSED'
    END                                 AS quota_status       -- CASE_WHEN
FROM orders o
JOIN sales_reps sr ON o.rep_id = sr.id
GROUP BY sr.id, sr.full_name, sr.region, sr.quota;


-- ---------------------------------------------------------------------------
-- 7. Executive Dashboard – Rolling 90-Day KPIs
--    sources: daily_revenue_kpi  →  target: exec_dashboard_kpis
--    Types: ALIAS, AGGREGATE_SUM, AGGREGATE_AVG, AGGREGATE_MAX, DERIVED
-- ---------------------------------------------------------------------------
INSERT INTO exec_dashboard_kpis (
    snapshot_date,
    revenue_90d,
    orders_90d,
    avg_daily_revenue,
    peak_daily_revenue,
    revenue_growth_pct
)
SELECT
    CURRENT_DATE                        AS snapshot_date,     -- DERIVED
    SUM(total_revenue)                  AS revenue_90d,       -- AGGREGATE_SUM
    SUM(order_count)                    AS orders_90d,        -- AGGREGATE_SUM
    AVG(total_revenue)                  AS avg_daily_revenue, -- AGGREGATE_AVG
    MAX(total_revenue)                  AS peak_daily_revenue,-- AGGREGATE_MAX
    (SUM(total_revenue) - LAG(SUM(total_revenue), 90)
        OVER (ORDER BY report_date))
        / NULLIF(LAG(SUM(total_revenue), 90)
        OVER (ORDER BY report_date), 0) AS revenue_growth_pct -- DERIVED
FROM daily_revenue_kpi
WHERE report_date >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY report_date;


-- ---------------------------------------------------------------------------
-- 8. Accounts Receivable Aging
--    sources: invoices, customers  →  target: ar_aging_report
--    Types: DIRECT, ALIAS, AGGREGATE_SUM, CASE_WHEN
-- ---------------------------------------------------------------------------
INSERT INTO ar_aging_report (
    customer_id,
    customer_name,
    current_due,
    overdue_30,
    overdue_60,
    overdue_90_plus,
    total_outstanding,
    risk_category
)
SELECT
    c.id                                AS customer_id,       -- ALIAS
    c.name                              AS customer_name,     -- ALIAS
    SUM(CASE WHEN i.days_overdue <= 0   THEN i.balance ELSE 0 END) AS current_due,    -- CASE_WHEN + AGGREGATE_SUM
    SUM(CASE WHEN i.days_overdue BETWEEN 1  AND 30 THEN i.balance ELSE 0 END) AS overdue_30,   -- CASE_WHEN + AGGREGATE_SUM
    SUM(CASE WHEN i.days_overdue BETWEEN 31 AND 60 THEN i.balance ELSE 0 END) AS overdue_60,   -- CASE_WHEN + AGGREGATE_SUM
    SUM(CASE WHEN i.days_overdue > 60   THEN i.balance ELSE 0 END) AS overdue_90_plus,-- CASE_WHEN + AGGREGATE_SUM
    SUM(i.balance)                      AS total_outstanding, -- AGGREGATE_SUM
    CASE
        WHEN MAX(i.days_overdue) > 90 THEN 'HIGH'
        WHEN MAX(i.days_overdue) > 30 THEN 'MEDIUM'
        ELSE 'LOW'
    END                                 AS risk_category      -- CASE_WHEN
FROM invoices i
JOIN customers c ON i.customer_id = c.id
GROUP BY c.id, c.name;
