#pragma once

#include <App.h>
#include <a0.h>

#include <memory>

#include "a0/api/options.hpp"
#include "a0/api/ws_common.hpp"

namespace a0::api {

// ws = new WebSocket(`ws://${api_addr}/wsapi/discover`)
// ws.onopen = () => {
//     ws.send(JSON.stringify({
//         protocol: "file",             // optional, one of "file", "pubsub", "rpc", "prpc", "log", "cfg"
//         topic: "**/*",                // optional
//         scheduler: "ON_DRAIN",        // optional, one of "IMMEDIATE", "ON_ACK", "ON_DRAIN"
//     }))
// }
// ws.onmessage = (evt) => {
//     ... evt.data ...
// }
struct WSDiscover {
  struct Data {
    std::shared_ptr<WSCommon> ws_common;
    std::unique_ptr<Discovery> discovery;
  };

  struct AlephZeroCallback {
    std::shared_ptr<WSCommon> ws_common;
    std::function<void(std::string)> send;

    const std::string protocol_tmpl;
    const std::string tmpl_key{"{topic}"};
    const size_t tmpl_key_idx;  // index of tmpl_key in protocol_tmpl.

    // Runs on uWS thread.
    template <typename WebSocket>
    AlephZeroCallback(WebSocket* ws, const RequestMessage& req_msg, std::string protocol_tmpl_)
        : ws_common{ws->getUserData()->ws_common},
          send{ws_common->bind_send(ws)},
          protocol_tmpl{std::move(protocol_tmpl_)},
          tmpl_key_idx{protocol_tmpl.find(tmpl_key)} {}

    // Runs on A0 thread.
    void operator()(const std::string& path) {
      if (!global()->running) {
        return;
      }

      std::string relpath = std::string(std::filesystem::relative(path, env::root()));

      std::string topic = relpath.substr(
          tmpl_key_idx,
          relpath.size() - (protocol_tmpl.size() - tmpl_key_idx - tmpl_key.size()));

      // Save the event count before sending the message.
      // Depending on the scheduler, the reader might block until the event counter increments.
      int64_t pre_send_cnt = ws_common->wake_cnt;

      send(nlohmann::json({
                              {"abspath", path},
                              {"relpath", relpath},
                              {"topic", topic},
                          })
               .dump());

      ws_common->wait(pre_send_cnt);
    }
  };

  static uWS::App::WebSocketBehavior<Data> behavior() {
    return {
        .compression = uWS::SHARED_COMPRESSOR,
        .maxPayloadLength = 16 * 1024 * 1024,
        .idleTimeout = 0,
        .maxBackpressure = 16 * 1024 * 1024,
        .closeOnBackpressureLimit = false,
        .resetIdleTimeoutOnSend = true,
        .upgrade = nullptr,
        .open = [](auto* ws) { global()->active_ws.insert(ws); },
        .message =
            [](auto* ws, std::string_view msg, uWS::OpCode code) {
              auto* data = ws->getUserData();
              if (!data->ws_common) {
                data->ws_common = std::make_shared<WSCommon>();
              }
              data->ws_common->OnMessageWithHandshake(
                  ws, msg, code, [ws, data](const RequestMessage& req_msg) {
                    req_msg.require("protocol");
                    req_msg.require("topic");

                    std::string protocol_tmpl = "{topic}";
                    req_msg.maybe_option_to("protocol", protocol_map(), protocol_tmpl);
                    std::string glob_path = std::filesystem::path(env::root()) / topic_path(protocol_tmpl, req_msg.topic);

                    data->discovery = std::make_unique<Discovery>(
                        glob_path, AlephZeroCallback(ws, req_msg, protocol_tmpl));
                  });
            },
        .drain =
            [](auto* ws) {
              auto* data = ws->getUserData();
              if (data->ws_common) {
                data->ws_common->ondrain(ws);
              }
            },
        .ping = nullptr,
        .pong = nullptr,
        .close =
            [](auto* ws, int code, std::string_view msg) {
              auto* data = ws->getUserData();
              if (data->ws_common) {
                data->ws_common->onclose(ws);
              }
            },
    };
  }
};

}  // namespace a0::api
