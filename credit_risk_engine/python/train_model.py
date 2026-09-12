"""
train_model.py
Loads customer_features from SQLite, does WOE/IV analysis, trains a
logistic regression credit scorecard, evaluates it (AUC, KS), and
exports the final coefficients to a JSON file that the C++ scoring
engine reads at runtime (so there's a single source of truth for the model).
"""

import sqlite3
import json
import os
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, roc_curve
from sklearn.preprocessing import StandardScaler

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "credit_risk.db")
WEIGHTS_PATH = os.path.join(os.path.dirname(__file__), "..", "cpp", "model_weights.json")

FEATURES = [
    "bureau_score",
    "credit_utilization",
    "debt_to_income",
    "years_employed",
    "credit_history_yrs",
    "num_credit_inquiries_6m",
    "max_dpd",
    "months_delinquent",
]


def load_data():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM customer_features", conn)
    conn.close()
    return df


def compute_iv(df, feature, target, bins=5):
    """Compute Information Value for a numeric feature via quantile binning."""
    try:
        df["_bin"] = pd.qcut(df[feature], bins, duplicates="drop")
    except ValueError:
        df["_bin"] = df[feature]

    grouped = df.groupby("_bin", observed=True)[target].agg(["count", "sum"])
    grouped.columns = ["total", "bad"]
    grouped["good"] = grouped["total"] - grouped["bad"]

    total_bad = grouped["bad"].sum()
    total_good = grouped["good"].sum()

    grouped["bad_rate"] = grouped["bad"] / total_bad.clip(1)
    grouped["good_rate"] = grouped["good"] / total_good.clip(1)
    # avoid div by zero / log(0)
    grouped["bad_rate"] = grouped["bad_rate"].replace(0, 1e-4)
    grouped["good_rate"] = grouped["good_rate"].replace(0, 1e-4)

    grouped["woe"] = np.log(grouped["good_rate"] / grouped["bad_rate"])
    grouped["iv"] = (grouped["good_rate"] - grouped["bad_rate"]) * grouped["woe"]

    df.drop(columns="_bin", inplace=True)
    return grouped["iv"].sum()


def run_iv_analysis(df):
    print("\n=== Information Value (feature strength) ===")
    iv_results = {}
    for f in FEATURES:
        iv = compute_iv(df.copy(), f, "default_flag")
        iv_results[f] = iv
    for f, iv in sorted(iv_results.items(), key=lambda x: -x[1]):
        strength = (
            "Suspicious/too strong" if iv > 0.5 else
            "Strong" if iv > 0.3 else
            "Medium" if iv > 0.1 else
            "Weak" if iv > 0.02 else
            "Not useful"
        )
        print(f"  {f:28s} IV={iv:.4f}  ({strength})")
    return iv_results


def train(df):
    X = df[FEATURES].copy()
    y = df["default_flag"].copy()

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    model = LogisticRegression(max_iter=1000, class_weight="balanced")
    model.fit(X_train_scaled, y_train)

    # Evaluate
    train_pred = model.predict_proba(X_train_scaled)[:, 1]
    test_pred = model.predict_proba(X_test_scaled)[:, 1]

    train_auc = roc_auc_score(y_train, train_pred)
    test_auc = roc_auc_score(y_test, test_pred)

    fpr, tpr, _ = roc_curve(y_test, test_pred)
    ks = max(tpr - fpr)

    print("\n=== Model Performance ===")
    print(f"  Train AUC: {train_auc:.4f}")
    print(f"  Test  AUC: {test_auc:.4f}")
    print(f"  Test  KS : {ks:.4f}  (KS > 0.4 is generally considered a strong scorecard)")

    return model, scaler, X_test, y_test, test_pred


def export_weights(model, scaler):
    """
    Export standardized-space coefficients converted back into raw-feature-space
    coefficients so the C++ engine can score raw feature values directly
    (no need to reimplement StandardScaler in C++):

        z_i = (x_i - mean_i) / std_i
        logit = b0 + sum(w_i * z_i)
                = b0 + sum(w_i * (x_i - mean_i)/std_i)
                = [b0 - sum(w_i * mean_i/std_i)] + sum[(w_i/std_i) * x_i]

    So raw-space weight_i = w_i / std_i
       raw-space intercept  = b0 - sum(w_i * mean_i / std_i)
    """
    w = model.coef_[0]
    b0 = model.intercept_[0]
    means = scaler.mean_
    stds = scaler.scale_

    raw_weights = w / stds
    raw_intercept = b0 - np.sum(w * means / stds)

    payload = {
        "features": FEATURES,
        "weights": raw_weights.tolist(),
        "intercept": float(raw_intercept),
        "note": "logit = intercept + sum(weights[i] * raw_feature[i]); "
                "probability = 1 / (1 + exp(-logit)); "
                "score = 300 + (1 - probability) * 600  [scaled to 300-900 like a bureau score]",
    }

    with open(WEIGHTS_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"\nExported model weights to {WEIGHTS_PATH}")


def export_test_set(X_test, y_test, test_pred, n=20):
    """Save a small sample of test cases with true label + python-predicted prob
    for cross-checking against the C++ engine's output."""
    out = X_test.copy()
    out["default_flag"] = y_test.values
    out["python_prob"] = test_pred
    sample = out.sample(n=n, random_state=1)
    sample_path = os.path.join(os.path.dirname(__file__), "..", "data", "test_sample.csv")
    sample.to_csv(sample_path, index=False)
    print(f"Exported {n}-row validation sample to {sample_path}")


def main():
    df = load_data()
    print(f"Loaded {len(df)} rows from customer_features")
    run_iv_analysis(df)
    model, scaler, X_test, y_test, test_pred = train(df)
    export_weights(model, scaler)
    export_test_set(X_test, y_test, test_pred)


if __name__ == "__main__":
    main()
