"""
benchmark_python_scoring.py
Runs the SAME row-by-row logistic scoring logic in pure Python (no vectorization,
mirroring how a naive application-layer service might call the model per-request)
so we can fairly compare against the C++ batch_score_benchmark throughput.
"""

import json
import time
import csv
import math
import os

WEIGHTS_PATH = os.path.join(os.path.dirname(__file__), "..", "cpp", "model_weights.json")
INPUT_CSV = os.path.join(os.path.dirname(__file__), "..", "data", "big_features.csv")


def load_model(path):
    with open(path) as f:
        payload = json.load(f)
    return payload["features"], payload["weights"], payload["intercept"]


def score_row(features_order, weights, intercept, row):
    logit = intercept
    for fname, w in zip(features_order, weights):
        logit += w * float(row[fname])
    prob = 1.0 / (1.0 + math.exp(-logit))
    score = round(300 + (1.0 - prob) * 600)
    return prob, score


def main():
    features_order, weights, intercept = load_model(WEIGHTS_PATH)

    with open(INPUT_CSV) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    start = time.perf_counter()
    results = []
    for row in rows:
        prob, score = score_row(features_order, weights, intercept, row)
        results.append((prob, score))
    end = time.perf_counter()

    ms = (end - start) * 1000
    print(f"Scored {len(rows)} applicants in {ms:.3f} ms (pure Python, row-by-row)")
    print(f"Throughput: {len(rows) / (ms / 1000):.0f} applicants/sec")


if __name__ == "__main__":
    main()
