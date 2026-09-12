// batch_score_benchmark.cpp
// Reads a CSV of applicants (same columns as the model features, in order),
// scores ALL of them, writes results to an output CSV, and reports timing —
// this is the piece that demonstrates why a bank would want a compiled
// scoring engine instead of running Python row-by-row in production:
// batch scoring thousands/millions of applicants needs to be fast.
//
// Usage:
//   ./batch_score_benchmark <weights.json> <input.csv> <output.csv>
//
// Input CSV must have a header row matching feature names (order-independent,
// extra columns like default_flag/python_prob are ignored/passed through).

#include <iostream>
#include <fstream>
#include <sstream>
#include <vector>
#include <string>
#include <unordered_map>
#include <chrono>
#include "scoring_model.hpp"

struct CsvData {
    std::vector<std::string> headers;
    std::vector<std::vector<std::string>> rows;
};

CsvData readCsv(const std::string& path) {
    CsvData data;
    std::ifstream file(path);
    if (!file.is_open()) throw std::runtime_error("Cannot open " + path);

    std::string line;
    std::getline(file, line);
    std::stringstream headerStream(line);
    std::string col;
    while (std::getline(headerStream, col, ',')) data.headers.push_back(col);

    while (std::getline(file, line)) {
        if (line.empty()) continue;
        std::vector<std::string> row;
        std::stringstream ss(line);
        std::string val;
        while (std::getline(ss, val, ',')) row.push_back(val);
        data.rows.push_back(row);
    }
    return data;
}

int main(int argc, char* argv[]) {
    if (argc != 4) {
        std::cerr << "Usage: " << argv[0] << " <weights.json> <input.csv> <output.csv>\n";
        return 1;
    }

    try {
        CreditScoringModel model(argv[1]);
        CsvData data = readCsv(argv[2]);

        // Map header name -> column index (done ONCE, not per row)
        std::unordered_map<std::string, size_t> colIndex;
        for (size_t i = 0; i < data.headers.size(); ++i) colIndex[data.headers[i]] = i;

        // Precompute, for each model feature (in order), which CSV column holds it.
        // This means the hot loop below does zero string hashing / map lookups —
        // just array indexing — which is the realistic way a production scoring
        // service would be written.
        std::vector<size_t> featureColumn;
        for (const auto& fname : model.featureNames()) {
            auto it = colIndex.find(fname);
            if (it == colIndex.end()) {
                std::cerr << "Warning: input CSV missing feature column '" << fname << "'\n";
                featureColumn.push_back(SIZE_MAX);
            } else {
                featureColumn.push_back(it->second);
            }
        }

        std::ofstream out(argv[3]);
        out << "row_id,probability_of_default,credit_score,risk_band\n";
        out.sync_with_stdio(false);

        std::vector<double> featureVec(featureColumn.size());

        auto start = std::chrono::high_resolution_clock::now();

        int rowId = 0;
        for (const auto& row : data.rows) {
            for (size_t i = 0; i < featureColumn.size(); ++i) {
                size_t col = featureColumn[i];
                if (col != SIZE_MAX && col < row.size()) {
                    featureVec[i] = std::atof(row[col].c_str());
                } else {
                    featureVec[i] = 0.0;
                }
            }
            ScoreResult r = model.scoreVector(featureVec);
            out << rowId << "," << r.probability_of_default << "," << r.credit_score << "," << r.risk_band << "\n";
            rowId++;
        }

        auto end = std::chrono::high_resolution_clock::now();
        double ms = std::chrono::duration<double, std::milli>(end - start).count();

        std::cout << "Scored " << rowId << " applicants in " << ms << " ms\n";
        std::cout << "Throughput: " << (rowId / (ms / 1000.0)) << " applicants/sec\n";
        std::cout << "Results written to " << argv[3] << "\n";

    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << "\n";
        return 1;
    }

    return 0;
}
