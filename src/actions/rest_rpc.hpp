#pragma once

#include <App.h>

#include <sstream>

#include "src/global_state.hpp"
#include "src/request_message.hpp"
#include "src/rest_helpers.hpp"

namespace a0::api {

// fetch(`http://${api_addr}/api/rpc`, {
//     method: "POST",
//     body: JSON.stringify({
//         container: "...",                 // required
//         topic: "...",                     // required
//         packet: {
//             headers: [                    // optional
//                 ["key", "val"],
//                 ...
//             ],
//             payload: window.btoa("..."),  // required
//         },
//         request_encoding: "base64"        // optional, one of "none", "base64"
//         response_encoding: "base64"       // optional, one of "none", "base64"
//     })
// })
// .then((r) => { return r.text() })
// .then((msg) => { console.log(msg) })
static inline void rest_rpc(uWS::HttpResponse<false>* res,
                            uWS::HttpRequest* req) {
  res->onData([res, ss = std::stringstream()](std::string_view chunk,
                                              bool is_end) mutable {
    ss << chunk;
    if (!is_end) {
      return;
    }

    RequestMessage req_msg;
    try {
      // Parse input.
      req_msg = ParseRequestMessage(ss.str());

      // Check required fields.
      req_msg.require("container");
      req_msg.require("topic");
      req_msg.require(nlohmann::json::json_pointer("/packet/payload"));
    } catch (std::exception& e) {
      rest_respond(res, "400", {}, e.what());
      return;
    }

    // Find the absolute topic.
    a0::TopicManager tm;
    tm.container = "unused";
    tm.rpc_client_aliases["target"] = {
        .container = req_msg.container,
        .topic = req_msg.topic,
    };

    // Perform requested action.
    // TODO(lshamis): This hurts! There must be a better way to manage the
    // memory here.
    auto* rpc_client = new a0::RpcClient(tm.rpc_client_topic("target"));
    rpc_client->send(std::move(req_msg.pkt), [res, rpc_client,
                                              encoder =
                                                  req_msg.response_encoder](
                                                 a0::PacketView pkt_view) {
      global()->event_loop->defer([res, hdrs = pkt_view.headers(),
                                   payload = encoder(pkt_view.payload())]() {
        nlohmann::json out = {
            {"headers", hdrs},
            {"payload", payload},
        };
        rest_respond(res, "200", {}, out.dump());
      });
      rpc_client->async_close([rpc_client]() { delete rpc_client; });
    });
  });

  res->onAborted([]() {});
}

}  // namespace a0::api
