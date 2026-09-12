-- Feature Engineering Queries
-- Joins customer, bureau, loan and repayment-behavior data into a single
-- model-ready table: customer_features

DROP VIEW IF EXISTS behavioral_features;
DROP TABLE IF EXISTS customer_features;

-- Step 1: Behavioral features derived from repayment history
-- (max DPD observed, average DPD, count of months with any delinquency)
CREATE VIEW behavioral_features AS
SELECT
    loan_id,
    MAX(days_past_due)                                   AS max_dpd,
    AVG(days_past_due)                                   AS avg_dpd,
    SUM(CASE WHEN days_past_due > 0 THEN 1 ELSE 0 END)   AS months_delinquent,
    AVG(CASE WHEN amount_due > 0 THEN amount_paid / amount_due ELSE 1 END) AS avg_payment_ratio
FROM repayment_history
GROUP BY loan_id;

-- Step 2: Master feature table joining everything, with derived ratios
CREATE TABLE customer_features AS
SELECT
    l.loan_id,
    c.customer_id,
    c.age,
    c.annual_income,
    c.employment_type,
    c.years_employed,
    c.city_tier,
    c.existing_emis,

    b.bureau_score,
    b.credit_history_yrs,
    b.num_open_loans,
    b.num_credit_inquiries_6m,
    ROUND(b.total_credit_used * 1.0 / NULLIF(b.total_credit_limit, 0), 4) AS credit_utilization,

    l.loan_type,
    l.loan_amount,
    l.tenure_months,
    l.interest_rate,
    ROUND(
        (c.existing_emis * 12 + l.loan_amount * 1.0 / (l.tenure_months / 12.0))
        / NULLIF(c.annual_income, 0), 4
    ) AS debt_to_income,

    COALESCE(bf.max_dpd, 0)              AS max_dpd,
    COALESCE(bf.avg_dpd, 0)              AS avg_dpd,
    COALESCE(bf.months_delinquent, 0)    AS months_delinquent,
    COALESCE(bf.avg_payment_ratio, 1.0)  AS avg_payment_ratio,

    l.default_flag
FROM loans l
JOIN customers c        ON c.customer_id = l.customer_id
JOIN bureau_scores b    ON b.customer_id = c.customer_id
LEFT JOIN behavioral_features bf ON bf.loan_id = l.loan_id;

-- Quick sanity check queries (run separately, not part of table build):
-- SELECT default_flag, COUNT(*), ROUND(AVG(bureau_score),0) FROM customer_features GROUP BY default_flag;
-- SELECT default_flag, ROUND(AVG(credit_utilization),3), ROUND(AVG(debt_to_income),3) FROM customer_features GROUP BY default_flag;
