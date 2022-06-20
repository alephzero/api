#pragma once

#include <App.h>

#include <memory>

#include "a0/api/options.hpp"
#include "a0/api/scope.hpp"
#include "a0/api/ws_common.hpp"

namespace a0::api {

// ws = new WebSocket(`ws://${api_addr}/wsapi/read`)
// ws.onopen = () => {
//     ws.send(JSON.stringify({
//         path: "...",                  // required
//         init: "AWAIT_NEW",            // optional, one of "OLDEST", "MOST_RECENT", "AWAIT_NEW"
//         iter: "NEXT",                 // optional, one of "NEXT", "NEWEST"
//         response_encoding: "none",    // optional, one of "none", "base64"
//         scheduler: "ON_DRAIN",        // optional, one of "IMMEDIATE", "ON_ACK", "ON_DRAIN"
//     }))
// }
// ws.onmessage = (evt) => {
//     ... evt.data ...
// }
struct WSRead {
  // Access and edit only in uWS thread.
  // Owns A0 thread.
  struct Data {
    std::shared_ptr<WSCommon> ws_common;
    std::unique_ptr<ReaderZeroCopy> reader;
  };

  struct AlephZeroCallback {
    std::shared_ptr<WSCommon> ws_common;
    std::function<std::string(std::string_view)> response_encoder;
    std::function<void(std::string)> send;
    std::function<void(int, std::string)> end;

    // Runs on uWS thread.
    template <typename WebSocket>
    AlephZeroCallback(WebSocket* ws, const RequestMessage& req_msg)
        : ws_common{ws->getUserData()->ws_common},
          response_encoder{req_msg.response_encoder},
          send{ws_common->bind_send(ws)},
          end{ws_common->bind_end(ws)} {}

    // Runs on A0 thread.
    void operator()(TransportLocked tlk, FlatPacket fpkt_cpp) {
      if (!global()->running) {
        return;
      }

      // Skip packets prior to seq_min.
      if (tlk.frame().hdr.seq <= ws_common->reader_seq_min) {
        return;
      }

      // Copy data out of the transport.
      // We can't use the data in the transport once we unlock.
      a0_flat_packet_t fpkt_c = *fpkt_cpp.c;
      std::vector<uint8_t> fpkt_copy_data(fpkt_c.buf.size);
      a0_flat_packet_t fpkt_copy{{fpkt_copy_data.data(), fpkt_c.buf.size}};
      memcpy(fpkt_copy.buf.data, fpkt_c.buf.data, fpkt_c.buf.size);

      // Unlock the transport. It needs to be relocked before the function returns.
      auto eos_relock_transport = scope_unlock_transport(*tlk.c);

      auto headers = strutil::flatten_headers(fpkt_copy);

      a0_buf_t payload_buf;
      a0_flat_packet_payload(fpkt_copy, &payload_buf);
      auto payload = response_encoder(string_view((const char*)payload_buf.data, payload_buf.size));

      // Save the event count before sending the message.
      // Depending on the scheduler, the reader might block until the event counter increments.
      int64_t pre_send_cnt = ws_common->wake_cnt;

      std::string to_send;
      try {
        to_send = nlohmann::json({
                                     {"headers", headers},
                                     {"payload", payload},
                                 })
                      .dump();
      } catch (std::exception& ex) {
        end(1011, ex.what());
        return;
      }

      send(std::move(to_send));

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
                    req_msg.require("path");
                    data->reader = std::make_unique<ReaderZeroCopy>(
                        File(req_msg.path), data->ws_common->reader_init, data->ws_common->reader_iter,
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
