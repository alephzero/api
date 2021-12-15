#pragma once

#include <App.h>

#include <sstream>

#include "a0/api/global_state.hpp"
#include "a0/api/request_message.hpp"
#include "a0/api/rest_helpers.hpp"

namespace a0::api {

// fetch(`http://${api_addr}/api/rpc`, {
//     method: "POST",
//     body: JSON.stringify({
//         topic: "...",                     // required
//         packet: {
//             headers: [                    // optional
//                 ["key", "val"],
//                 ...
//             ],
//             payload: "...",               // required
//         },
//         request_encoding: "none",         // optional, one of "none", "base64"
//         response_encoding: "none",        // optional, one of "none", "base64"
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
      req_msg.require("topic");
      req_msg.require(nlohmann::json::json_pointer("/packet/payload"));
    } catch (std::exception& e) {
      rest_respond(res, "400", {}, e.what());
      return;
    }

    // Perform requested action.
    // TODO(lshamis): This hurts! There must be a better way to manage the
    // memory here.
    auto* rpc_client = new RpcClient(req_msg.topic);

    auto callback = [res, rpc_client, req_msg](Packet pkt) {
      global()->event_loop->defer([res, rpc_client, pkt, req_msg]() {
        nlohmann::json out = {
            {"headers", strutil::flatten(pkt.headers())},
            {"payload", req_msg.response_encoder(pkt.payload())},
        };
        rest_respond(res, "200", {}, out.dump());
        delete rpc_client;
      });
    };

    rpc_client->send(std::move(req_msg.pkt), callback);
  });

  res->onAborted([]() {});
}

}  // namespace a0::api
