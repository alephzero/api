#pragma once

#include <cstdlib>
#include <string_view>

static inline std::string_view env(std::string_view key,
                                   std::string_view default_) {
  const char* val = std::getenv(key.data());
  return val ? val : default_;
}
