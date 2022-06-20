#pragma once

#include <App.h>

#include <memory>

#include "a0/api/options.hpp"
#include "a0/api/ws_common.hpp"

namespace a0::api {

// ws = new WebSocket(`ws://${api_addr}/wsapi/log`)
// ws.onopen = () => {
//     ws.send(JSON.stringify({
//         topic: "...",                 // required
//         level: "INFO",                // optional, one of "DBG", "INFO", "WARN", "ERR", "CRIT"
//         init: "AWAIT_NEW",            // optional, one of "OLDEST", "MOST_RECENT", "AWAIT_NEW"
//         iter: "NEXT",                 // optional, one of "NEXT", "NEWEST"
//         response_encoding: "none",    // optional, one of "none", "base64"
//         scheduler: "ON_DRAIN",        // optional, one of "IMMEDIATE", "ON_ACK", "ON_DRAIN"
//     }))
// }
// ws.onmessage = (evt) => {
//     ... evt.data ...
// }
struct WSLog {
  struct Data {
    std::shared_ptr<WSCommon> ws_common;
    std::unique_ptr<LogListener> listener;
  };

  struct AlephZeroCallback {
    std::shared_ptr<WSCommon> ws_common;
    std::function<std::string(std::string_view)> response_encoder;
    std::function<void(std::string)> send;

    // Runs on uWS thread.
    template <typename WebSocket>
    AlephZeroCallback(WebSocket* ws, const RequestMessage& req_msg)
        : ws_common{ws->getUserData()->ws_common},
          response_encoder{req_msg.response_encoder},
          send{ws_common->bind_send(ws)} {}

    // Runs on A0 thread.
    void operator()(Packet pkt) {
      if (!global()->running) {
        return;
      }

      // TODO: Should we handle reader_seq_min here?

      auto headers = strutil::flatten(pkt.headers());
      auto payload = response_encoder(pkt.payload());

      // Save the event count before sending the message.
      // Depending on the scheduler, the log listener might block until the event counter increments.
      int64_t pre_send_cnt = ws_common->wake_cnt;

      send(nlohmann::json({
                              {"headers", headers},
                              {"payload", payload},
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
                    req_msg.require("topic");

                    LogLevel level = LogLevel::INFO;
                    req_msg.maybe_option_to("level", level_map(), level);

                    data->listener = std::make_unique<LogListener>(
                        req_msg.topic, level, data->ws_common->reader_init, data->ws_common->reader_iter,
                        AlephZeroCallback(ws, req_msg));
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
