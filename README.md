# Credit Risk Scoring Engine — End-to-End Project

A complete credit risk scorecard system built to demonstrate the full stack a
bank's risk/credit team would actually use: **SQL** for the data layer,
**Python** for modeling, and **C++** for a production-speed scoring engine.

This was built for an ICICI Bank consulting internship to show engineering
depth beyond a typical Excel/PowerPoint deliverable.

---

## Architecture

```
                 ┌─────────────────────┐
                 │   SQLite Database    │
                 │  (schema.sql)        │
                 │  customers, loans,   │
                 │  bureau_scores,      │
                 │  repayment_history   │
                 └──────────┬───────────┘
                            │
                  SQL feature engineering
                     (features.sql)
                            │
                            ▼
                 ┌─────────────────────┐
                 │  customer_features   │
                 │  (model-ready table) │
                 └──────────┬───────────┘
                            │
                  Python (train_model.py)
              IV analysis → Logistic Regression
              → AUC/KS evaluation → export weights
                            │
                            ▼
                 ┌─────────────────────┐
                 │ model_weights.json   │
                 └──────────┬───────────┘
                            │
              C++ Scoring Engine (cpp/)
        ┌───────────────────┴───────────────────┐
        │                                        │
   score_cli.cpp                     batch_score_benchmark.cpp
   (single applicant,                (bulk scoring at
    real-time use case)               production throughput)
```

## Folder Structure

```
credit_risk_engine/
├── sql/
│   ├── schema.sql          # Database schema (customers, loans, bureau, repayments)
│   └── features.sql        # Feature engineering: joins + derived ratios (DTI, utilization)
├── python/
│   ├── generate_data.py    # Generates 5,000 synthetic but realistic customer/loan records
│   ├── train_model.py      # WOE/IV analysis, logistic regression, exports weights
│   └── benchmark_python_scoring.py  # Pure-Python scoring loop for speed comparison
├── cpp/
│   ├── json_lite.hpp       # Minimal dependency-free JSON reader (no external libs needed)
│   ├── scoring_model.hpp   # Core logistic scoring logic
│   ├── score_cli.cpp       # CLI: score one applicant
│   ├── batch_score_benchmark.cpp  # Batch scorer + throughput benchmark
│   └── model_weights.json  # Exported model coefficients (Python → C++ handoff)
├── data/
│   ├── credit_risk.db      # SQLite database (generated)
│   ├── full_features.csv   # Full feature export for batch scoring
│   └── test_sample.csv     # 20-row validation sample with Python's predicted probabilities
└── README.md
```

---

## How to Run It End-to-End

```bash
# 1. Generate synthetic data and build the SQLite database
cd python
python3 generate_data.py

# 2. Build the feature table (SQL joins + derived ratios)
python3 -c "
import sqlite3
conn = sqlite3.connect('../data/credit_risk.db')
conn.executescript(open('../sql/features.sql').read())
conn.commit()
"

# 3. Train the model, run IV analysis, export weights for C++
python3 train_model.py

# 4. Compile the C++ scoring engine
cd ../cpp
g++ -O2 -std=c++17 -o score_cli score_cli.cpp
g++ -O2 -std=c++17 -o batch_score_benchmark batch_score_benchmark.cpp

# 5a. Score a single applicant (real-time use case)
./score_cli model_weights.json 720 0.25 0.35 5.0 6.0 1 0 0

# 5b. Batch-score a whole file (production throughput use case)
./batch_score_benchmark model_weights.json ../data/full_features.csv ../data/scored_output.csv
```

---

## Data Model (SQL)

Four tables, mirroring what a real bank's core banking + bureau systems would expose:

| Table | Purpose |
|---|---|
| `customers` | Demographics: age, income, employment type, city tier |
| `bureau_scores` | Credit bureau snapshot: score, credit history length, utilization inputs |
| `loans` | The loan being underwritten: amount, tenure, rate, and the **target label** (`default_flag`) |
| `repayment_history` | Month-by-month DPD (days past due) — used to derive behavioral features |

`features.sql` joins these into a single `customer_features` table with derived
ratios that are the actual inputs to the model:

- **`credit_utilization`** = credit used / credit limit
- **`debt_to_income`** = (existing EMIs + new loan EMI) / annual income
- Behavioral aggregates from repayment history: `max_dpd`, `months_delinquent`, `avg_payment_ratio`

---

## Model (Python)

- **Information Value (IV) analysis** — a standard credit-risk technique to
  rank feature strength before modeling. On this dataset:

  | Feature | IV | Strength |
  |---|---|---|
  | bureau_score | 0.32 | Strong |
  | credit_utilization | 0.29 | Medium |
  | debt_to_income | 0.26 | Medium |
  | years_employed | 0.13 | Medium |
  | credit_history_yrs | 0.11 | Medium |
  | num_credit_inquiries_6m | 0.01 | Not useful |

- **Model:** Logistic Regression (class-balanced, standardized features)
- **Performance:** Test AUC ≈ **0.75**, KS statistic ≈ **0.37** — a reasonably
  strong scorecard for a first-pass model (real bank scorecards typically
  target AUC 0.75–0.85 and KS > 0.4 after further feature engineering).
- **Weight export:** coefficients are converted from standardized space back
  into raw-feature space, so the C++ engine can score raw applicant data
  directly without reimplementing `StandardScaler`.

---

## Scoring Engine (C++)

Two programs, both reading the same `model_weights.json` so there is a single
source of truth for the model:

1. **`score_cli`** — scores one applicant at a time. Simulates a real-time
   loan origination system calling a scoring microservice.
2. **`batch_score_benchmark`** — scores an entire CSV of applicants and
   reports throughput. Simulates nightly/batch risk re-scoring of a loan book.

**Correctness check:** C++ output matches Python's `predict_proba` to within
~4×10⁻⁷ (floating-point rounding only) — verified on a held-out validation
sample.

**Performance (1,000,000 applicants):**

| Implementation | Time | Throughput |
|---|---|---|
| Pure Python (row-by-row) | 1,823 ms | ~549,000 applicants/sec |
| C++ (compiled, `-O2`) | 784 ms | ~1,275,000 applicants/sec |

The C++ engine is **~2.3x faster** at this scale even in a best-case Python
loop; the gap grows further in realistic production conditions (per-request
overhead, concurrent load, memory pressure) — which is the actual argument
for why a bank would compile the hot scoring path rather than run it in
Python or a notebook.

---

## What This Demonstrates for the Internship

- **SQL:** relational schema design, joins, derived-feature queries — the kind
  of data engineering a bank's risk team relies on before any model gets built.
- **Python:** the standard credit-risk modeling workflow (IV/WOE, logistic
  regression, AUC/KS evaluation) that risk analysts actually use.
- **C++:** translating a model into a fast, dependency-free production
  component — the piece most interns never show, and the one that makes this
  look like an engineering deliverable rather than just an analysis.
- **End-to-end thinking:** data → features → model → deployment → benchmark,
  which is the full lifecycle a consulting recommendation would need to
  address credibly (it's not enough to say "build a scorecard" — you have to
  show it can actually run at bank scale).

## Caveats to State Upfront in Any Presentation

- All data is **synthetic**, generated with a hidden logistic function plus
  noise — it demonstrates the pipeline, not real ICICI risk patterns.
- AUC/KS are believable but not claims about real portfolio performance.
- A real deployment would need model governance, fairness/bias testing,
  monitoring for drift, and regulatory sign-off (RBI model risk management
  guidelines) — worth mentioning as "next steps" in any writeup.
