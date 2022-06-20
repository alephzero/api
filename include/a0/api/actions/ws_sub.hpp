#pragma once

#include <App.h>

#include <memory>

#include "a0/api/options.hpp"
#include "a0/api/scope.hpp"
#include "a0/api/ws_common.hpp"

namespace a0::api {

// ws = new WebSocket(`ws://${api_addr}/wsapi/sub`)
// ws.onopen = () => {
//     ws.send(JSON.stringify({
//         topic: "...",                 // required
//         init: "AWAIT_NEW",            // optional, one of "OLDEST", "MOST_RECENT", "AWAIT_NEW"
//         iter: "NEXT",                 // optional, one of "NEXT", "NEWEST"
//         response_encoding: "none",    // optional, one of "none", "base64"
//         scheduler: "ON_DRAIN",        // optional, one of "IMMEDIATE", "ON_ACK", "ON_DRAIN"
//     }))
// }
// ws.onmessage = (evt) => {
//     ... evt.data ...
// }
struct WSSub {
  struct Data {
    std::shared_ptr<WSCommon> ws_common;
    std::unique_ptr<SubscriberZeroCopy> sub;
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
                    data->sub = std::make_unique<SubscriberZeroCopy>(
                        req_msg.topic, data->ws_common->reader_init, data->ws_common->reader_iter,
                        WSRead::AlephZeroCallback(ws, req_msg));
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
