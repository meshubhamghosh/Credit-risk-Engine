"""
generate_data.py
Generates synthetic but realistic customer/loan/bureau/repayment data
and loads it into the SQLite database defined in sql/schema.sql.

Default flag is generated using a hidden "true" risk function with noise,
so the downstream model has real signal to learn (not pure randomness).
"""

import sqlite3
import numpy as np
import os

np.random.seed(42)

N_CUSTOMERS = 5000
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "credit_risk.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "..", "sql", "schema.sql")


def build_schema(conn):
    with open(SCHEMA_PATH, "r") as f:
        conn.executescript(f.read())
    conn.commit()


def generate_customers(n):
    age = np.random.randint(21, 65, n)
    employment_type = np.random.choice(
        ["SALARIED", "SELF_EMPLOYED", "BUSINESS"], n, p=[0.6, 0.25, 0.15]
    )
    # income correlated loosely with age and employment type
    base_income = np.random.lognormal(mean=13.2, sigma=0.5, size=n)  # ~ INR 3L-15L range
    income_multiplier = np.where(employment_type == "BUSINESS", 1.3,
                          np.where(employment_type == "SELF_EMPLOYED", 1.1, 1.0))
    annual_income = np.round(base_income * income_multiplier, -3)

    years_employed = np.clip(np.random.normal(loc=(age - 21) * 0.4, scale=2.5), 0, 40)
    city_tier = np.random.choice([1, 2, 3], n, p=[0.4, 0.35, 0.25])
    existing_emis = np.round(np.random.exponential(scale=8000, size=n), -2)

    return {
        "age": age,
        "annual_income": annual_income,
        "employment_type": employment_type,
        "years_employed": np.round(years_employed, 1),
        "city_tier": city_tier,
        "existing_emis": existing_emis,
    }


def generate_bureau(n, annual_income, years_employed):
    credit_history_yrs = np.clip(np.random.normal(loc=years_employed * 0.7, scale=2), 0, 30)
    num_open_loans = np.random.poisson(lam=1.5, size=n)
    num_inquiries = np.random.poisson(lam=1.2, size=n)
    total_credit_limit = np.round(annual_income * np.random.uniform(0.3, 1.2, n), -3)
    utilization = np.clip(np.random.beta(2, 5, n), 0, 1)
    total_credit_used = np.round(total_credit_limit * utilization, -2)

    # bureau score: higher history, lower utilization, fewer inquiries -> higher score
    raw = (
        650
        + credit_history_yrs * 4
        - utilization * 150
        - num_inquiries * 15
        - num_open_loans * 5
        + np.random.normal(0, 25, n)
    )
    bureau_score = np.clip(raw, 300, 900).astype(int)

    return {
        "bureau_score": bureau_score,
        "credit_history_yrs": np.round(credit_history_yrs, 1),
        "num_open_loans": num_open_loans,
        "num_credit_inquiries_6m": num_inquiries,
        "total_credit_limit": total_credit_limit,
        "total_credit_used": total_credit_used,
    }


def generate_loans_and_default(n, cust, bureau):
    loan_type = np.random.choice(["PERSONAL", "MSME", "AUTO", "HOME"], n, p=[0.45, 0.2, 0.2, 0.15])
    loan_amount = np.round(cust["annual_income"] * np.random.uniform(0.2, 1.5, n), -3)
    tenure_months = np.random.choice([12, 24, 36, 48, 60], n)
    interest_rate = np.round(np.random.uniform(9.5, 18.5, n), 2)

    utilization = bureau["total_credit_used"] / np.maximum(bureau["total_credit_limit"], 1)
    dti = (cust["existing_emis"] * 12 + loan_amount / (tenure_months / 12)) / np.maximum(cust["annual_income"], 1)

    # Hidden "true" risk score (logit) driving default probability.
    # Lower bureau score, higher utilization, higher DTI, fewer years employed -> higher default risk.
    logit = (
        -4.0
        - 0.006 * (bureau["bureau_score"] - 650)
        + 2.8 * utilization
        + 1.6 * dti
        - 0.05 * cust["years_employed"]
        + 0.3 * (cust["employment_type"] == "SELF_EMPLOYED")
        + 0.5 * (cust["employment_type"] == "BUSINESS")
        + 0.02 * bureau["num_credit_inquiries_6m"]
    )
    prob_default = 1 / (1 + np.exp(-logit))
    default_flag = (np.random.uniform(0, 1, n) < prob_default).astype(int)

    disbursement_dates = np.random.choice(
        [f"2023-{m:02d}-01" for m in range(1, 13)] + [f"2024-{m:02d}-01" for m in range(1, 13)], n
    )

    return {
        "loan_type": loan_type,
        "loan_amount": loan_amount,
        "tenure_months": tenure_months,
        "interest_rate": interest_rate,
        "disbursement_date": disbursement_dates,
        "default_flag": default_flag,
    }, dti, utilization


def generate_repayment_history(conn, loan_ids, default_flags, tenures):
    rows = []
    for loan_id, is_default, tenure in zip(loan_ids, default_flags, tenures):
        months_observed = min(tenure, 12)  # observe up to 12 months of history
        dpd_running = 0
        for m in range(1, months_observed + 1):
            if is_default:
                # defaulted loans show escalating delinquency over time
                if m > months_observed - 4:
                    dpd_running = min(dpd_running + np.random.randint(15, 45), 180)
                else:
                    dpd_running = max(0, dpd_running + np.random.randint(-5, 20))
            else:
                dpd_running = max(0, dpd_running + np.random.randint(-3, 4))
                dpd_running = min(dpd_running, 29)  # good accounts stay under 30 DPD

            amount_due = round(np.random.uniform(2000, 40000), 2)
            shortfall_factor = 0.0 if dpd_running == 0 else np.random.uniform(0.1, 0.6)
            amount_paid = round(amount_due * (1 - shortfall_factor), 2)

            rows.append((loan_id, m, int(dpd_running), amount_paid, amount_due))

    conn.executemany(
        "INSERT INTO repayment_history (loan_id, month_number, days_past_due, amount_paid, amount_due) "
        "VALUES (?, ?, ?, ?, ?)",
        rows,
    )


def main():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    build_schema(conn)

    n = N_CUSTOMERS
    cust = generate_customers(n)
    bureau = generate_bureau(n, cust["annual_income"], cust["years_employed"])
    loans, dti, utilization = generate_loans_and_default(n, cust, bureau)

    customer_ids = np.arange(1, n + 1)
    loan_ids = np.arange(1, n + 1)  # one loan per customer for simplicity

    conn.executemany(
        "INSERT INTO customers VALUES (?,?,?,?,?,?,?)",
        list(zip(
            customer_ids.tolist(),
            cust["age"].tolist(),
            cust["annual_income"].tolist(),
            cust["employment_type"].tolist(),
            cust["years_employed"].tolist(),
            cust["city_tier"].tolist(),
            cust["existing_emis"].tolist(),
        )),
    )

    conn.executemany(
        "INSERT INTO bureau_scores VALUES (?,?,?,?,?,?,?)",
        list(zip(
            customer_ids.tolist(),
            bureau["bureau_score"].tolist(),
            bureau["credit_history_yrs"].tolist(),
            bureau["num_open_loans"].tolist(),
            bureau["num_credit_inquiries_6m"].tolist(),
            bureau["total_credit_limit"].tolist(),
            bureau["total_credit_used"].tolist(),
        )),
    )

    conn.executemany(
        "INSERT INTO loans VALUES (?,?,?,?,?,?,?,?)",
        list(zip(
            loan_ids.tolist(),
            customer_ids.tolist(),
            loans["loan_type"].tolist(),
            loans["loan_amount"].tolist(),
            loans["tenure_months"].tolist(),
            loans["interest_rate"].tolist(),
            loans["disbursement_date"].tolist(),
            loans["default_flag"].tolist(),
        )),
    )

    generate_repayment_history(conn, loan_ids, loans["default_flag"], loans["tenure_months"])

    conn.commit()

    default_rate = loans["default_flag"].mean()
    print(f"Generated {n} customers/loans into {DB_PATH}")
    print(f"Overall default rate: {default_rate:.2%}")
    conn.close()


if __name__ == "__main__":
    main()
