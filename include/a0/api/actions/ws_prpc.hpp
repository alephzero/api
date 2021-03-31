#pragma once

#include <App.h>

#include <memory>

#include "a0/api/options.hpp"

namespace a0::api {

// ws = new WebSocket(`ws://${api_addr}/wsapi/prpc`)
// ws.onopen = () => {
//     ws.send(JSON.stringify({
//         container: "...",             // required
//         topic: "...",                 // required
//         iter: "NEXT",                 // optional, one of "NEXT", "NEWEST"
//         request_encoding: "base64",   // optional, one of "none", "base64"
//         response_encoding: "base64",  // optional, one of "none", "base64"
//         scheduler: "IMMEDIATE",       // optional, one of "IMMEDIATE", "ON_ACK", "ON_DRAIN"
//     }))
// }
// ws.onmessage = (evt) => {
//     ... evt.data ...
// }
struct WSPrpc {
  struct Data {
    std::unique_ptr<a0::PrpcClient> client;
    a0_subscriber_iter_t iter{A0_ITER_NEXT};
    scheduler_t scheduler{scheduler_t::IMMEDIATE};
    std::shared_ptr<std::atomic<int64_t>> scheduler_event_count{std::make_shared<std::atomic<int64_t>>(0)};
    std::string connection_id;

    // If iter is A0_ITER_NEWEST.
    struct NewestPkt {
      std::optional<a0::Packet> pkt;
      bool done;
      std::mutex mtx;
    };
    std::shared_ptr<NewestPkt> newest_pkt{std::make_shared<NewestPkt>()};
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

              auto* data = (WSPrpc::Data*)ws->getUserData();

              // If the handshake is complete, and scheduler is ON_ACK, and message is "ACK", unblock the next message.
              if (data->client && data->scheduler == scheduler_t::ON_ACK && msg == "ACK") {
                (*data->scheduler_event_count)++;
                global()->cv.notify_all();
                return;
              }

              // Check the handshake hasn't already happend.
              if (data->client) {
                ws->end(4000,
                        "Rpc Client has already been created. Only one allowed "
                        "per websocket.");
                return;
              }

              // Parse the request, including common fields.
              RequestMessage req_msg;
              try {
                req_msg = ParseRequestMessage(msg);
                req_msg.require("container");
                req_msg.require("topic");
              } catch (std::exception& e) {
                ws->end(4000, e.what());
                return;
              }

              // Get the required 'iter' option.
              try {
                req_msg.maybe_option_to("iter", iter_map(), data->iter);
              } catch (std::exception& e) {
                ws->end(4000, e.what());
                return;
              }

              // Get the optional 'scheduler' option.
              try {
                req_msg.maybe_option_to("scheduler", scheduler_map(), data->scheduler);
              } catch (std::exception& e) {
                ws->end(4000, e.what());
                return;
              }

              // Find the absolute topic.
              a0::TopicManager tm;
              tm.container = "unused";
              tm.prpc_client_aliases["target"] = {
                  .container = req_msg.container,
                  .topic = req_msg.topic,
              };
              auto topic = tm.prpc_client_topic("target");

              // Create the prpc.
              data->client = std::make_unique<a0::PrpcClient>(topic);
              data->connection_id = std::string(req_msg.pkt.id());

              // Note: we don't want to use the "ws" or "data" directly in the prpc thread.
              data->client->connect(std::move(req_msg.pkt), [ws, req_msg,
                                                             iter = data->iter,
                                                             scheduler = data->scheduler,
                                                             curr_cnt = data->scheduler_event_count,
                                                             newest_pkt = data->newest_pkt](const a0::PacketView& pkt_view, bool done) {
                if (!global()->running) {
                  return;
                }

                // Save the event count before sending the message.
                // Depending on the scheduler, the client might block until
                // the event counter increments.
                int64_t pre_send_cnt = *curr_cnt;

                // Save views and perform work we don't want to do on the
                // event loop.
                auto headers = pkt_view.headers();
                auto payload = req_msg.response_encoder(pkt_view.payload());
                if (iter == A0_ITER_NEWEST) {
                  std::unique_lock<std::mutex> lk{newest_pkt->mtx};
                  newest_pkt->pkt = a0::Packet(headers, payload);
                  newest_pkt->done = done;
                }

                // Schedule the event loop to perform the send operation.
                // We can use "ws" or "data" within the event loop, assuming
                // the ws is still alive.
                global()->event_loop->defer([ws, done,
                                             headers = std::move(headers),
                                             payload = std::move(payload)]() {
                  // Make sure the ws hasn't closed between the sub
                  // callback and this task.
                  if (!global()->running ||
                      !global()->active_ws.count(ws)) {
                    return;
                  }

                  auto* data = (WSPrpc::Data*)ws->getUserData();

                  if (data->iter == A0_ITER_NEXT) {
                    ws->send(nlohmann::json({
                                                {"headers", headers},
                                                {"payload", payload},
                                                {"done", done},
                                            })
                                 .dump(),
                             uWS::TEXT, true);
                  } else if (data->iter == A0_ITER_NEWEST) {
                    std::unique_lock<std::mutex> lk{data->newest_pkt->mtx};
                    if (!data->newest_pkt->pkt) {
                      return;
                    }
                    ws->send(nlohmann::json({
                                                {"headers", data->newest_pkt->pkt->headers()},
                                                {"payload", data->newest_pkt->pkt->payload()},
                                                {"done", data->newest_pkt->done},
                                            })
                                 .dump(),
                             uWS::TEXT, true);
                    data->newest_pkt->pkt = std::nullopt;
                  }
                });

                // Maybe block subscriber callback thread.
                if (iter == A0_ITER_NEXT && scheduler != scheduler_t::IMMEDIATE) {
                  std::unique_lock<std::mutex> lk{global()->mu};
                  global()->cv.wait(lk, [pre_send_cnt, curr_cnt]() {
                    // Unblock if:
                    // * system is shutting down.
                    // * websocket is closing (indicated by -1).
                    // * the scheduler is ready for the next message.
                    return !global()->running || *curr_cnt == -1 ||
                           pre_send_cnt < *curr_cnt;
                  });
                }
              });
            },
        .drain =
            [](auto* ws) {
              auto* data = (WSPrpc::Data*)ws->getUserData();
              if (data->scheduler == scheduler_t::ON_DRAIN && ws->getBufferedAmount() == 0) {
                (*data->scheduler_event_count)++;
                global()->cv.notify_all();
              }
            },
        .ping = nullptr,
        .pong = nullptr,
        .close =
            [](auto* ws, int code, std::string_view msg) {
              auto* data = (WSPrpc::Data*)ws->getUserData();
              *data->scheduler_event_count = -1;
              if (data->client) {
                data->client->cancel(data->connection_id);
              }
              global()->active_ws.erase(ws);
              global()->cv.notify_all();
            },
    };
  }
};

}  // namespace a0::api
