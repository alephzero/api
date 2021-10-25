#pragma once

#include <a0.h>

#include "a0/bridge/sink.hpp"
#include "a0/bridge/source.hpp"

namespace a0::api {

static inline
std::string replace_all(std::string str, const std::string& search, const std::string& replace) {
  size_t pos = 0;
  while((pos = str.find(search, pos)) != std::string::npos) {
    str.replace(pos, search.size(), replace);
    pos += replace.size();
  }
  return str;
}

struct LocalAlephZeroTarget {
  enum struct Protocol {
    FILE,
    CFG,
    LOG,
    PRPC,
    PUBSUB,
    RPC,
  } protocol;
  std::string topic;

  File file() const {
    std::map<Protocol, std::string> tmpl_map{
        {Protocol::FILE, "{topic}"},
        {Protocol::CFG, a0_env_topic_tmpl_cfg()},
        {Protocol::LOG, a0_env_topic_tmpl_log()},
        {Protocol::PRPC, a0_env_topic_tmpl_prpc()},
        {Protocol::PUBSUB, a0_env_topic_tmpl_pubsub()},
        {Protocol::RPC, a0_env_topic_tmpl_rpc()},
    };

    return File(replace_all(tmpl_map[protocol], "{topic}", topic));
  }
};

NLOHMANN_JSON_SERIALIZE_ENUM(LocalAlephZeroTarget::Protocol, {
  {LocalAlephZeroTarget::Protocol::FILE, "file"},
  {LocalAlephZeroTarget::Protocol::CFG, "cfg"},
  {LocalAlephZeroTarget::Protocol::LOG, "log"},
  {LocalAlephZeroTarget::Protocol::PRPC, "prpc"},
  {LocalAlephZeroTarget::Protocol::PUBSUB, "pubsub"},
  {LocalAlephZeroTarget::Protocol::RPC, "rpc"},
});

static inline
void from_json(const nlohmann::json& j, LocalAlephZeroTarget& l) {
  j.at("protocol").get_to(l.protocol);
  j.at("topic").get_to(l.topic);
}

class AlephZeroSource : public Source::Base {
  Sink sink;
  Reader reader;

 public:
  AlephZeroSource(nlohmann::json args, Sink sink_) : sink(std::move(sink_)) {
    reader = Reader(
        args.get<LocalAlephZeroTarget>().file(),
        A0_INIT_AWAIT_NEW,
        A0_ITER_NEXT,
        [this](Packet pkt) mutable {
          sink(pkt);
        });
  }
};

REGISTER_SOURCE(alephzero, AlephZeroSource);
REGISTER_SOURCE(a0, AlephZeroSource);

class AlephZeroSink : public Sink::Base {
  Writer writer;

 public:
  AlephZeroSink(nlohmann::json args) {
    writer = Writer(args.get<LocalAlephZeroTarget>().file());
  }

  void operator()(Packet pkt) override {
    writer.write(pkt);
  }
};

REGISTER_SINK(alephzero, AlephZeroSink);
REGISTER_SINK(a0, AlephZeroSink);

}  // namespace a0::api
