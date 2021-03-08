#pragma once

#include <string>
#include <string_view>
#include <utility>

namespace base64 {

constexpr std::string_view kCharSet =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

inline static std::string encode(std::string_view input) {
  std::string out;

  int a = 0, b = -6;
  for (auto c : input) {
    a = (a << 8) + c;
    b += 8;
    while (b >= 0) {
      out.push_back(kCharSet[(a >> b) & 0x3F]);
      b -= 6;
    }
  }
  if (b > -6) {
    out.push_back(kCharSet[((a << 8) >> (b + 8)) & 0x3F]);
  }
  while (out.size() % 4) {
    out.push_back('=');
  }
  return out;
}

inline static std::string decode(std::string_view input) {
  static const std::array<int, 256> table = []() {
    std::array<int, 256> table_builder;
    for (auto& elem : table_builder) {
      elem = -1;
    }
    for (int i = 0; i < 64; i++) {
      table_builder[kCharSet[i]] = i;
    }
    return table_builder;
  }();

  std::string out;

  int a = 0, b = -8;
  for (auto c : input) {
    if (table[c] == -1) {
      break;
    }
    a = (a << 6) + table[c];
    b += 6;
    if (b >= 0) {
      out.push_back(char((a >> b) & 0xFF));
      b -= 8;
    }
  }
  return out;
}

}  // namespace base64

inline static const std::
    unordered_map<std::string, std::function<std::string(std::string_view)>>&
    Encoders() {
  static const std::unordered_map<std::string,
                                  std::function<std::string(std::string_view)>>
      // Default to base64 for backwards compatability.
      enc = {
          {"", &base64::encode},
          {"none", [](std::string_view str) { return std::string(str); }},
          {"base64", &base64::encode},
      };
  return enc;
}

inline static const std::
    unordered_map<std::string, std::function<std::string(std::string_view)>>&
    Decoders() {
  static const std::unordered_map<std::string,
                                  std::function<std::string(std::string_view)>>
      // Default to base64 for backwards compatability.
      dec = {
          {"", &base64::decode},
          {"none", [](std::string_view str) { return std::string(str); }},
          {"base64", &base64::decode},
      };
  return dec;
}
