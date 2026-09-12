// score_cli.cpp
// Command-line credit scoring tool.
//
// Usage:
//   ./score_cli <weights.json> <bureau_score> <credit_utilization> <debt_to_income>
//               <years_employed> <credit_history_yrs> <num_credit_inquiries_6m>
//               <max_dpd> <months_delinquent>
//
// Example:
//   ./score_cli model_weights.json 720 0.25 0.35 5.0 6.0 1 0 0
//
// Prints the logit, default probability, 300-900 score, and risk band —
// simulating how a real-time loan origination system would call a compiled
// scoring service instead of a Python script.

#include <iostream>
#include <vector>
#include <string>
#include "scoring_model.hpp"

int main(int argc, char* argv[]) {
    if (argc != 10) {
        std::cerr << "Usage: " << argv[0]
                  << " <weights.json> <bureau_score> <credit_utilization> <debt_to_income> "
                  << "<years_employed> <credit_history_yrs> <num_credit_inquiries_6m> "
                  << "<max_dpd> <months_delinquent>\n";
        return 1;
    }

    try {
        CreditScoringModel model(argv[1]);

        std::vector<double> features;
        for (int i = 2; i < argc; ++i) {
            features.push_back(std::stod(argv[i]));
        }

        ScoreResult result = model.scoreVector(features);

        std::cout << "----------------------------------------\n";
        std::cout << " Credit Scoring Engine (C++) \n";
        std::cout << "----------------------------------------\n";
        std::cout << "Logit                : " << result.logit << "\n";
        std::cout << "Probability of default: " << (result.probability_of_default * 100) << "%\n";
        std::cout << "Credit Score (300-900): " << result.credit_score << "\n";
        std::cout << "Risk Band             : " << result.risk_band << "\n";

    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << "\n";
        return 1;
    }

    return 0;
}
