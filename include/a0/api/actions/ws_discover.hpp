#pragma once

#include <App.h>
#include <a0.h>

#include <memory>

#include "a0/api/options.hpp"

namespace a0::api {

// ws = new WebSocket(`ws://${api_addr}/wsapi/discover`)
// ws.onopen = () => {
//     ws.send(JSON.stringify({
//         protocol: "...",              // required, one of "file", "pubsub", "rpc", "prpc", "log", "cfg"
//         topic: "**/*",                // optional
//         scheduler: "IMMEDIATE",       // optional, one of "IMMEDIATE", "ON_ACK", "ON_DRAIN"
//     }))
// }
// ws.onmessage = (evt) => {
//     ... evt.data ...
// }
struct WSDiscover {
  struct Data {
    bool init{false};
    scheduler_t scheduler{scheduler_t::IMMEDIATE};
    std::shared_ptr<std::atomic<int64_t>> scheduler_event_count{std::make_shared<std::atomic<int64_t>>(0)};

    std::unique_ptr<Discovery> discovery;
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
                req_msg.require("protocol");
                req_msg.require("topic");
              } catch (std::exception& e) {
                ws->end(4000, e.what());
                return;
              }

              static std::unordered_map<std::string, std::string> protocol_map = {
                  {"file", "{topic}"},
                  {"cfg", env::topic_tmpl_cfg()},
                  {"log", env::topic_tmpl_log()},
                  {"prpc", env::topic_tmpl_prpc()},
                  {"pubsub", env::topic_tmpl_pubsub()},
                  {"rpc", env::topic_tmpl_rpc()},
              };

              // Get the required 'protocol' option.
              std::string glob_path;
              std::string protocol_tmpl = "**/*";
              try {
                req_msg.maybe_option_to("protocol", protocol_map, protocol_tmpl);
                glob_path = std::filesystem::path(env::root()) / topic_path(protocol_tmpl, req_msg.topic);
              } catch (std::exception& e) {
                ws->end(4000, e.what());
                return;
              }
              const std::string tmpl_topic = "{topic}";
              const size_t tmpl_topic_idx = protocol_tmpl.find(tmpl_topic);

              // Get the optional 'scheduler' option.
              try {
                req_msg.maybe_option_to("scheduler", scheduler_map(), data->scheduler);
              } catch (std::exception& e) {
                ws->end(4000, e.what());
                return;
              }

              // Create the discovery.
              // Note: we don't want to use the "ws" or "data" directly in the discovery thread.
              data->discovery = std::make_unique<Discovery>(
                  glob_path,
                  [ws, req_msg, protocol_tmpl, tmpl_topic, tmpl_topic_idx,
                   scheduler = data->scheduler,
                   curr_cnt = data->scheduler_event_count](const std::string& path) {
                    if (!global()->running) {
                      return;
                    }

                    // Save the event count before sending the message.
                    // Depending on the scheduler, the discovery might block until the event counter increments.
                    int64_t pre_send_cnt = *curr_cnt;

                    // Schedule the event loop to perform the send operation.
                    // We can use "ws" or "data" within the event loop, assuming the ws is still alive.
                    global()->event_loop->defer(
                        [ws, req_msg, path, protocol_tmpl, tmpl_topic, tmpl_topic_idx]() {
                          // Make sure the ws hasn't closed between the discovery callback and this task.
                          if (!global()->running ||
                              !global()->active_ws.count(ws)) {
                            return;
                          }

                          std::string relpath = std::string(std::filesystem::relative(path, env::root()));

                          std::string topic = relpath.substr(
                              tmpl_topic_idx,
                              relpath.size() - (protocol_tmpl.size() - tmpl_topic_idx - tmpl_topic.size()));

                          auto send_status = ws->send(nlohmann::json{
                                                          {"abspath", path},
                                                          {"relpath", relpath},
                                                          {"topic", topic},
                                                      }
                                                          .dump(),
                                                      uWS::TEXT, true);

                          auto* data = ws->getUserData();
                          if (data->scheduler == scheduler_t::ON_DRAIN && send_status == ws->SUCCESS) {
                            (*data->scheduler_event_count)++;
                            global()->cv.notify_all();
                          }
                        });

                    // Maybe block discovery callback thread.
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
