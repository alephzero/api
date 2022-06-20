#pragma once

#include <App.h>

#include <memory>

#include "a0/api/options.hpp"

namespace a0::api {

// ws = new WebSocket(`ws://${api_addr}/wsapi/prpc`)
// ws.onopen = () => {
//     ws.send(JSON.stringify({
//         topic: "...",                 // required
//         iter: "NEXT",                 // optional, one of "NEXT", "NEWEST"
//         request_encoding: "none",     // optional, one of "none", "base64"
//         response_encoding: "none",    // optional, one of "none", "base64"
//         scheduler: "ON_DRAIN",        // optional, one of "IMMEDIATE", "ON_ACK", "ON_DRAIN"
//     }))
// }
// ws.onmessage = (evt) => {
//     ... evt.data ...
// }
struct WSPrpc {
  struct AlephZeroCallback {
    std::shared_ptr<WSCommon> ws_common;
    std::function<void(std::string)> send;
    std::function<std::string(std::string_view)> response_encoder;

    // If iter is ITER_NEWEST.
    struct NewestPkt {
      std::optional<Packet> pkt;
      bool done;
      bool ready_to_send{true};
      std::mutex mtx;
    };
    std::shared_ptr<NewestPkt> newest_pkt{std::make_shared<NewestPkt>()};

    // Runs on uWS thread.
    template <typename WebSocket>
    AlephZeroCallback(WebSocket* ws, const RequestMessage& req_msg)
        : ws_common{ws->getUserData()->ws_common},
          send{ws_common->bind_send(ws)},
          response_encoder{req_msg.response_encoder} {}

    void do_send(Packet pkt, bool done) {
      send(nlohmann::json({
                              {"headers", strutil::flatten(pkt.headers())},
                              {"payload", response_encoder(pkt.payload())},
                              {"done", done},
                          })
               .dump());
    }

    void send_newest_locked() {
      newest_pkt->ready_to_send = true;
      if (!newest_pkt->pkt) {
        return;
      }

      do_send(*newest_pkt->pkt, newest_pkt->done);

      newest_pkt->ready_to_send = ws_common->sched == scheduler_t::IMMEDIATE;
      newest_pkt->pkt = std::nullopt;
    }

    void send_newest() {
      std::unique_lock<std::mutex> lk{newest_pkt->mtx};
      send_newest_locked();
    }

    // Runs on A0 thread.
    void operator()(Packet pkt, bool done) {
      if (!global()->running) {
        return;
      }

      if (ws_common->reader_iter == ITER_NEXT) {
        // Save the event count before sending the message.
        // Depending on the scheduler, the log listener might block until the event counter increments.
        int64_t pre_send_cnt = ws_common->wake_cnt;
        do_send(pkt, done);
        ws_common->wait(pre_send_cnt);
      } else if (ws_common->reader_iter == ITER_NEWEST) {
        {
          std::unique_lock<std::mutex> lk{newest_pkt->mtx};
          newest_pkt->pkt = pkt;
          newest_pkt->done = done;
          if (newest_pkt->ready_to_send) {
            send_newest_locked();
          }
        }
      }
    }
  };

  struct Data {
    std::shared_ptr<WSCommon> ws_common;
    std::unique_ptr<PrpcClient> client;
    std::string connection_id;
    std::unique_ptr<AlephZeroCallback> alephzero_callback;
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

                    data->client = std::make_unique<PrpcClient>(req_msg.topic);
                    data->connection_id = std::string(req_msg.pkt.id());
                    data->alephzero_callback = std::make_unique<AlephZeroCallback>(ws, req_msg);
                    if (data->ws_common->reader_iter == ITER_NEWEST) {
                      data->ws_common->wake_hook = [data]() {
                        data->alephzero_callback->send_newest();
                      };
                    }
                    data->client->connect(
                        std::move(req_msg.pkt),
                        [data](Packet pkt, bool done) {
                          (*data->alephzero_callback)(std::move(pkt), done);
                        });
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
              if (data->client) {
                data->client->cancel(data->connection_id);
              }
              if (data->ws_common) {
                data->ws_common->onclose(ws);
              }
            },
    };
  }
};

}  // namespace a0::api
