#pragma once

#include <App.h>

#include <memory>

#include "a0/api/options.hpp"

namespace a0::api {

// ws = new WebSocket(`ws://${api_addr}/wsapi/read`)
// ws.onopen = () => {
//     ws.send(JSON.stringify({
//         path: "...",                  // required
//         init: "...",                  // required, one of "OLDEST", "MOST_RECENT", "AWAIT_NEW"
//         iter: "...",                  // required, one of "NEXT", "NEWEST"
//         response_encoding: "none",    // optional, one of "none", "base64"
//         scheduler: "IMMEDIATE",       // optional, one of "IMMEDIATE", "ON_ACK", "ON_DRAIN"
//     }))
// }
// ws.onmessage = (evt) => {
//     ... evt.data ...
// }
struct WSRead {
  struct Data {
    bool init{false};
    scheduler_t scheduler{scheduler_t::IMMEDIATE};
    std::shared_ptr<std::atomic<int64_t>> scheduler_event_count{std::make_shared<std::atomic<int64_t>>(0)};

    std::unique_ptr<Reader> reader;
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
              if (code != uWS::OpCode::TEXT) {
                return;
              }

              auto* data = ws->getUserData();

              // If the handshake is complete, and scheduler is ON_ACK, and message is "ACK", unblock the next message.
              if (data->init && data->scheduler == scheduler_t::ON_ACK && msg == std::string_view("ACK")) {
                (*data->scheduler_event_count)++;
                global()->cv.notify_all();
                return;
              }

              // Check the handshake hasn't already happend.
              if (data->init) {
                ws->end(4000, "Handshake only allowed once per websocket.");
                return;
              }
              data->init = true;

              // Parse the request, including common fields.
              RequestMessage req_msg;
              try {
                req_msg = ParseRequestMessage(msg);
                req_msg.require("path");
              } catch (std::exception& e) {
                ws->end(4000, e.what());
                return;
              }

              // Get the required 'init' option.
              a0_reader_init_t init;
              try {
                req_msg.require_option_to("init", init_map(), init);
              } catch (std::exception& e) {
                ws->end(4000, e.what());
                return;
              }

              // Get the required 'iter' option.
              a0_reader_iter_t iter;
              try {
                req_msg.require_option_to("iter", iter_map(), iter);
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

              // Create the reader.
              // Note: we don't want to use the "ws" or "data" directly in the reader thread.
              data->reader = std::make_unique<Reader>(
                  File(req_msg.path), init, iter,
                  [ws, req_msg,
                   scheduler = data->scheduler,
                   curr_cnt = data->scheduler_event_count](Packet pkt) {
                    if (!global()->running) {
                      return;
                    }

                    // Save the event count before sending the message.
                    // Depending on the scheduler, the reader might block until the event counter increments.
                    int64_t pre_send_cnt = *curr_cnt;

                    // Save views and perform work we don't want to do on the
                    // event loop.
                    auto headers = strutil::flatten(pkt.headers());
                    auto payload = req_msg.response_encoder(pkt.payload());

                    // Schedule the event loop to perform the send operation.
                    // We can use "ws" or "data" within the event loop, assuming the ws is still alive.
                    global()->event_loop->defer(
                        [ws,
                         headers = std::move(headers),
                         payload = std::move(payload)]() {
                          // Make sure the ws hasn't closed between the reader callback and this task.
                          if (!global()->running ||
                              !global()->active_ws.count(ws)) {
                            return;
                          }
                          auto send_status = ws->send(nlohmann::json(
                                                          {
                                                              {"headers", headers},
                                                              {"payload", payload},
                                                          })
                                                          .dump(),
                                                      uWS::TEXT, true);

                          auto* data = ws->getUserData();
                          if (data->scheduler == scheduler_t::ON_DRAIN && send_status == ws->SUCCESS) {
                            (*data->scheduler_event_count)++;
                            global()->cv.notify_all();
                          }
                        });

                    // Maybe block reader callback thread.
                    if (scheduler != scheduler_t::IMMEDIATE) {
                      std::unique_lock<std::mutex> lk{global()->mu};
                      global()->cv.wait(lk, [pre_send_cnt, curr_cnt]() {
                        // Unblock if:
                        // * system is shutting down.
                        // * websocket is closing (indicated by -1).
                        // * the scheduler is ready for the next message.
                        return !global()->running || *curr_cnt == -1 || pre_send_cnt < *curr_cnt;
                      });
                    }
                  });
            },
        .drain =
            [](auto* ws) {
              auto* data = ws->getUserData();
              if (data->scheduler == scheduler_t::ON_DRAIN && ws->getBufferedAmount() == 0) {
                (*data->scheduler_event_count)++;
                global()->cv.notify_all();
              }
            },
        .ping = nullptr,
        .pong = nullptr,
        .close =
            [](auto* ws, int code, std::string_view msg) {
              auto* data = ws->getUserData();
              *data->scheduler_event_count = -1;
              global()->active_ws.erase(ws);
              global()->cv.notify_all();
            },
    };
  }
};

}  // namespace a0::api
