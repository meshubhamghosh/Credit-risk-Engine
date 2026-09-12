-- Credit Risk Scoring Engine — Database Schema
-- SQLite dialect (portable; same structure translates directly to MySQL/PostgreSQL)

DROP TABLE IF EXISTS repayment_history;
DROP TABLE IF EXISTS loans;
DROP TABLE IF EXISTS bureau_scores;
DROP TABLE IF EXISTS customers;

-- Core customer demographic/profile table
CREATE TABLE customers (
    customer_id     INTEGER PRIMARY KEY,
    age             INTEGER NOT NULL,
    annual_income   REAL NOT NULL,          -- in INR
    employment_type TEXT NOT NULL,          -- SALARIED / SELF_EMPLOYED / BUSINESS
    years_employed  REAL NOT NULL,
    city_tier       INTEGER NOT NULL,       -- 1, 2, or 3
    existing_emis   REAL NOT NULL DEFAULT 0 -- total monthly EMI outflow before this loan
);

-- Credit bureau data (like a simplified CIBIL record)
CREATE TABLE bureau_scores (
    customer_id         INTEGER PRIMARY KEY REFERENCES customers(customer_id),
    bureau_score        INTEGER NOT NULL,      -- 300-900 scale
    credit_history_yrs  REAL NOT NULL,
    num_open_loans      INTEGER NOT NULL,
    num_credit_inquiries_6m INTEGER NOT NULL,
    total_credit_limit  REAL NOT NULL,
    total_credit_used   REAL NOT NULL          -- for utilization ratio
);

-- Loan applications / accounts
CREATE TABLE loans (
    loan_id         INTEGER PRIMARY KEY,
    customer_id     INTEGER NOT NULL REFERENCES customers(customer_id),
    loan_type       TEXT NOT NULL,          -- PERSONAL / MSME / AUTO / HOME
    loan_amount     REAL NOT NULL,
    tenure_months   INTEGER NOT NULL,
    interest_rate   REAL NOT NULL,
    disbursement_date TEXT NOT NULL,
    default_flag    INTEGER NOT NULL        -- 1 = defaulted (90+ DPD), 0 = good standing (TARGET LABEL)
);

-- Monthly repayment history (used for behavioral features)
CREATE TABLE repayment_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    loan_id         INTEGER NOT NULL REFERENCES loans(loan_id),
    month_number    INTEGER NOT NULL,
    days_past_due   INTEGER NOT NULL DEFAULT 0,
    amount_paid     REAL NOT NULL,
    amount_due      REAL NOT NULL
);

CREATE INDEX idx_loans_customer ON loans(customer_id);
CREATE INDEX idx_repay_loan ON repayment_history(loan_id);
