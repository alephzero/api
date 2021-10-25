#pragma once

#include "a0/bridge/sink.hpp"
#include "a0/bridge/source.hpp"

namespace a0::api {

using Pipe = Source;

struct Bridge {
  std::map<std::string, std::unique_ptr<Pipe>> pipes;

  void add_pipe(std::string name, Source::Config source_config, Sink::Config sink_config) {
    pipes[name] = std::make_unique<Pipe>(source_config, Sink(sink_config));
  }

  void del_pipe(std::string name) {
    pipes.erase(name);
  }
};

}  // namespace a0::api
