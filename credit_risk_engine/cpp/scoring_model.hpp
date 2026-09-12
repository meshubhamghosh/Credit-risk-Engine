// scoring_model.hpp
// Core credit scoring logic: loads logistic regression weights exported by
// train_model.py and computes default probability + a 300-900 bureau-style
// score for a given feature vector. Designed for speed — no allocations in
// the hot scoring path, weights loaded once at startup.

#pragma once
#include <vector>
#include <string>
#include <cmath>
#include <unordered_map>
#include "json_lite.hpp"

struct ScoreResult {
    double logit;
    double probability_of_default;
    int    credit_score;       // scaled 300-900
    std::string risk_band;     // LOW / MEDIUM / HIGH / VERY_HIGH
};

class CreditScoringModel {
public:
    explicit CreditScoringModel(const std::string& weightsPath) {
        std::string text = jsonlite::readFile(weightsPath);

        std::string featBlock = jsonlite::extractArrayBlock(text, "features");
        std::string weightBlock = jsonlite::extractArrayBlock(text, "weights");

        featureNames_ = jsonlite::parseStringArray(featBlock);
        weights_ = jsonlite::parseDoubleArray(weightBlock);
        intercept_ = jsonlite::extractNumber(text, "intercept");

        if (featureNames_.size() != weights_.size()) {
            throw std::runtime_error("Feature/weight count mismatch in " + weightsPath);
        }

        for (size_t i = 0; i < featureNames_.size(); ++i) {
            featureIndex_[featureNames_[i]] = i;
        }
    }

    const std::vector<std::string>& featureNames() const { return featureNames_; }

    // Score using a feature vector in the SAME ORDER as featureNames().
    ScoreResult scoreVector(const std::vector<double>& features) const {
        if (features.size() != weights_.size()) {
            throw std::runtime_error("Feature vector size mismatch");
        }
        double logit = intercept_;
        for (size_t i = 0; i < weights_.size(); ++i) {
            logit += weights_[i] * features[i];
        }
        return buildResult(logit);
    }

    // Score using a named map — more convenient for CLI/API use, slightly slower.
    ScoreResult scoreMap(const std::unordered_map<std::string, double>& featureMap) const {
        double logit = intercept_;
        for (size_t i = 0; i < featureNames_.size(); ++i) {
            auto it = featureMap.find(featureNames_[i]);
            double val = (it != featureMap.end()) ? it->second : 0.0;
            logit += weights_[i] * val;
        }
        return buildResult(logit);
    }

private:
    ScoreResult buildResult(double logit) const {
        double prob = 1.0 / (1.0 + std::exp(-logit));
        // Higher prob of default -> lower score. Scale to 300-900 like a bureau score.
        int score = static_cast<int>(std::round(300 + (1.0 - prob) * 600));

        std::string band;
        if (score >= 750) band = "LOW";
        else if (score >= 650) band = "MEDIUM";
        else if (score >= 550) band = "HIGH";
        else band = "VERY_HIGH";

        return ScoreResult{logit, prob, score, band};
    }

    std::vector<std::string> featureNames_;
    std::vector<double> weights_;
    double intercept_;
    std::unordered_map<std::string, size_t> featureIndex_;
};
