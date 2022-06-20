#pragma once

#include <App.h>
#include <a0.h>

#include <sstream>

#include "a0/api/global_state.hpp"
#include "a0/api/request_message.hpp"
#include "a0/api/rest_common.hpp"

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
A0_STATIC_INLINE
void rest_rpc(uWS::HttpResponse<false>* res,
              uWS::HttpRequest* req) {
  rest_common(res, req, [res](const RequestMessage& req_msg) {
    // Check required fields.
    req_msg.require("topic");
    req_msg.require(nlohmann::json::json_pointer("/packet/payload"));

    // Perform requested action.

    // rpc_client's lifetime must run until the callback fires.
    // The rpc_client CANNOT be freed in the rpc_client's callback.
    auto rpc_client = std::make_shared<RpcClient>(req_msg.topic);

    auto callback = [res, req_msg, rpc_client](Packet pkt) {
      global()->event_loop->defer([res, req_msg, rpc_client, pkt]() {
        try {
          rest_respond(res, "200", {}, nlohmann::json{
                                           {"headers", strutil::flatten(pkt.headers())},
                                           {"payload", req_msg.response_encoder(pkt.payload())},
                                       }
                                           .dump());
        } catch (std::exception& e) {
          rest_respond(res, "400", {}, e.what());
        }
      });
    };

    rpc_client->send(std::move(req_msg.pkt), callback);
  });
}

}  // namespace a0::api
