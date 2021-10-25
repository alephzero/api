#pragma once

#include <functional>
#include <memory>
#include <nlohmann/json.hpp>

#include "a0/bridge/sink.hpp"

namespace a0::api {

class Source final {
public:
  struct Config {
    std::string type;
    nlohmann::json args;
  };

  struct Base {
    virtual ~Base() = default;
  };

  using Factory = std::function<std::unique_ptr<Base>(nlohmann::json, Sink)>;

  static std::map<std::string, Factory>* registrar() {
    static std::map<std::string, Factory> r;
    return &r;
  }

  static bool register_(std::string key, Factory fact) {
    return registrar()->insert({std::move(key), std::move(fact)}).second;
  }

  Source(Config config, Sink sink) {
    base = registrar()->at(config.type)(config.args, std::move(sink));
  }

private:
  std::unique_ptr<Base> base;
};

A0_STATIC_INLINE
void from_json(const nlohmann::json& j, Source::Config& s) {
  j.at("type").get_to(s.type);
  if (j.count("args")) {
    s.args = j.at("args");
  }
}

}  // namespace a0::api

#define REGISTER_SOURCE(key, clz) \
  static bool _ ## clz ## __ ## key = a0::api::Source::register_(#key, [](nlohmann::json args, a0::api::Sink sink) { return std::make_unique<clz>(args, std::move(sink)); });
