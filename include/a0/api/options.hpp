#pragma once

#include <a0.h>

#include <unordered_map>

namespace a0::api {

enum struct scheduler_t {
  IMMEDIATE,
  ON_ACK,
  ON_DRAIN,
};

const std::unordered_map<std::string, scheduler_t>& scheduler_map() {
  static std::unordered_map<std::string, scheduler_t> val = {
      {"IMMEDIATE", scheduler_t::IMMEDIATE},
      {"ON_ACK", scheduler_t::ON_ACK},
      {"ON_DRAIN", scheduler_t::ON_DRAIN},
  };
  return val;
}

const std::unordered_map<std::string, Reader::Init>& init_map() {
  static std::unordered_map<std::string, Reader::Init> val = {
      {"OLDEST", INIT_OLDEST},
      {"MOST_RECENT", INIT_MOST_RECENT},
      {"AWAIT_NEW", INIT_AWAIT_NEW},
  };
  return val;
}

const std::unordered_map<std::string, Reader::Iter>& iter_map() {
  static std::unordered_map<std::string, Reader::Iter> val = {
      {"NEXT", ITER_NEXT},
      {"NEWEST", ITER_NEWEST},
  };
  return val;
}

const std::unordered_map<std::string, LogLevel>& level_map() {
  static std::unordered_map<std::string, LogLevel> val = {
      {"CRIT", LogLevel::CRIT},
      {"ERR", LogLevel::ERR},
      {"WARN", LogLevel::WARN},
      {"INFO", LogLevel::INFO},
      {"DBG", LogLevel::DBG},
  };
  return val;
}

}  // namespace a0::api
