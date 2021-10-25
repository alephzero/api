#pragma once

#include <a0.h>
#include <functional>
#include <memory>
#include <nlohmann/json.hpp>

namespace a0::api {

class Sink final {
public:
  struct Config {
    std::string type;
    nlohmann::json args;
  };

  struct Base {
    virtual ~Base() = default;
    virtual void operator()(Packet) = 0;
  };

  using Factory = std::function<std::unique_ptr<Base>(nlohmann::json)>;

  static std::map<std::string, Factory>* registrar() {
    static std::map<std::string, Factory> r;
    return &r;
  }

  static bool register_(std::string key, Factory fact) {
    return registrar()->insert({std::move(key), std::move(fact)}).second;
  }

  Sink(Config config) {
    base = registrar()->at(config.type)(config.args);
  }

  void operator()(Packet pkt) { (*base)(pkt); }

private:
  std::unique_ptr<Base> base;
};

A0_STATIC_INLINE
void from_json(const nlohmann::json& j, Sink::Config& s) {
  j.at("type").get_to(s.type);
  if (j.count("args")) {
    s.args = j.at("args");
  }
}

}  // namespace a0::api

#define REGISTER_SINK(key, clz) \
  static bool _ ## clz ## __ ## key = a0::api::Sink::register_(#key, [](nlohmann::json args) { return std::make_unique<clz>(args); });
