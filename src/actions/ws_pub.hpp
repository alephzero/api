#pragma once

#include <App.h>

#include <memory>

namespace a0::api {

// ws = new WebSocket(`ws://${api_addr}/wsapi/pub`)
// ws.onopen = () => {
//     ws.send(JSON.stringify({
//         container: "...",            // required
//         topic: "...",                // required
//         request_encoding: "base64"   // optional, one of "none", "base64"
//         response_encoding: "base64"  // optional, one of "none", "base64"
//     }))
// }
// // later, after onopen completes:
// ws.send(JSON.stringify({
//         packet: {
//             headers: [                    // optional
//                 ["key", "val"],
//                 ...
//             ],
//             payload: window.btoa("..."),  // required
//         },
// }))
struct WSPub {
  struct Data {
    std::unique_ptr<a0::Publisher> publisher;
  };

  static uWS::App::WebSocketBehavior behavior() {
    return {
        .compression = uWS::SHARED_COMPRESSOR,
        .maxPayloadLength = 16 * 1024 * 1024,
        .idleTimeout = 300,
        .maxBackpressure = 16 * 1024 * 1024,
        .closeOnBackpressureLimit = false,
        .resetIdleTimeoutOnSend = true,
        .upgrade = nullptr,
        .open = [](auto* ws) { global()->active_ws.insert(ws); },
        .message =
            [](auto* ws, std::string_view msg, uWS::OpCode code) {
              if (code != uWS::OpCode::TEXT) {
                return;
              }

              auto* data = (WSPub::Data*)ws->getUserData();

              // Parse input.
              RequestMessage req_msg;
              try {
                req_msg = ParseRequestMessage(msg);
              } catch (std::exception& e) {
                ws->end(4000, e.what());
                return;
              }

              // Is this the handshake message?
              if (!data->publisher) {
                // Require container/topic.
                try {
                  req_msg.require("container");
                  req_msg.require("topic");
                } catch (std::exception& e) {
                  ws->end(4000, e.what());
                  return;
                }

                // Find the absolute topic.
                a0::TopicManager tm;
                tm.container = req_msg.container;
                data->publisher = std::make_unique<a0::Publisher>(
                    tm.publisher_topic(req_msg.topic));
              } else {
                // Require packet.
                try {
                  req_msg.require(
                      nlohmann::json::json_pointer("/packet/payload"));
                } catch (std::exception& e) {
                  ws->end(4000, e.what());
                  return;
                }

                data->publisher->pub(req_msg.pkt);
              }
            },
        .drain = nullptr,
        .ping = nullptr,
        .pong = nullptr,
        .close =
            [](auto* ws, int code, std::string_view msg) {
              global()->active_ws.erase(ws);
              global()->cv.notify_all();
            },
    };
  }
};

}  // namespace a0::api
