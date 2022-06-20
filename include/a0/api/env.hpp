#pragma once

#include <a0.h>

#include <cstdlib>
#include <string_view>

namespace a0::api {

A0_STATIC_INLINE
std::string_view env(std::string_view key,
                     std::string_view default_) {
  const char* val = std::getenv(key.data());
  return val ? val : default_;
}

}  // namespace a0::api
