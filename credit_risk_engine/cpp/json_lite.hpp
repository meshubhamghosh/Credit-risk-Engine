// json_lite.hpp
// A minimal, dependency-free JSON reader — just enough to parse the specific
// flat structure produced by train_model.py's export_weights() function:
//   { "features": ["a","b",...], "weights": [0.1, -0.2,...], "intercept": 1.23, "note": "..." }
//
// This is NOT a general-purpose JSON parser. It's deliberately narrow so the
// C++ scoring engine has zero external dependencies (no nlohmann/json, no
// internet fetch needed) while still reading the exact file Python writes.

#pragma once
#include <string>
#include <vector>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <cctype>

namespace jsonlite {

inline std::string readFile(const std::string& path) {
    std::ifstream f(path);
    if (!f.is_open()) {
        throw std::runtime_error("Could not open file: " + path);
    }
    std::stringstream ss;
    ss << f.rdbuf();
    return ss.str();
}

// Extracts the raw text between the first '[' and matching ']' following a given key.
inline std::string extractArrayBlock(const std::string& text, const std::string& key) {
    std::string pattern = "\"" + key + "\"";
    size_t keyPos = text.find(pattern);
    if (keyPos == std::string::npos) throw std::runtime_error("Key not found: " + key);

    size_t start = text.find('[', keyPos);
    if (start == std::string::npos) throw std::runtime_error("Array start not found for key: " + key);

    int depth = 0;
    size_t i = start;
    for (; i < text.size(); ++i) {
        if (text[i] == '[') depth++;
        else if (text[i] == ']') {
            depth--;
            if (depth == 0) break;
        }
    }
    return text.substr(start + 1, i - start - 1);
}

inline std::vector<double> parseDoubleArray(const std::string& block) {
    std::vector<double> result;
    std::stringstream ss(block);
    std::string token;
    while (std::getline(ss, token, ',')) {
        // strip whitespace
        size_t s = token.find_first_not_of(" \t\n\r");
        size_t e = token.find_last_not_of(" \t\n\r");
        if (s == std::string::npos) continue;
        token = token.substr(s, e - s + 1);
        if (!token.empty()) result.push_back(std::stod(token));
    }
    return result;
}

inline std::vector<std::string> parseStringArray(const std::string& block) {
    std::vector<std::string> result;
    bool inQuotes = false;
    std::string current;
    for (char c : block) {
        if (c == '"') {
            if (inQuotes) {
                result.push_back(current);
                current.clear();
            }
            inQuotes = !inQuotes;
        } else if (inQuotes) {
            current += c;
        }
    }
    return result;
}

inline double extractNumber(const std::string& text, const std::string& key) {
    std::string pattern = "\"" + key + "\"";
    size_t keyPos = text.find(pattern);
    if (keyPos == std::string::npos) throw std::runtime_error("Key not found: " + key);
    size_t colon = text.find(':', keyPos);
    size_t end = text.find_first_of(",}\n", colon + 1);
    std::string numStr = text.substr(colon + 1, end - colon - 1);
    // strip whitespace
    size_t s = numStr.find_first_not_of(" \t\n\r");
    size_t e = numStr.find_last_not_of(" \t\n\r");
    numStr = numStr.substr(s, e - s + 1);
    return std::stod(numStr);
}

} // namespace jsonlite
