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

const std::unordered_map<std::string, a0_reader_init_t>& init_map() {
  static std::unordered_map<std::string, a0_reader_init_t> val = {
      {"OLDEST", A0_INIT_OLDEST},
      {"MOST_RECENT", A0_INIT_MOST_RECENT},
      {"AWAIT_NEW", A0_INIT_AWAIT_NEW},
  };
  return val;
}

const std::unordered_map<std::string, a0_reader_iter_t>& iter_map() {
  static std::unordered_map<std::string, a0_reader_iter_t> val = {
      {"NEXT", A0_ITER_NEXT},
      {"NEWEST", A0_ITER_NEWEST},
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
