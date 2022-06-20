#pragma once

#include <App.h>
#include <a0.h>

#include <sstream>

#include "a0/api/request_message.hpp"
#include "a0/api/rest_common.hpp"

namespace a0::api {

// fetch(`http://${api_addr}/api/pub`, {
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
//     })
// })
// .then((r) => { return r.text() })
// .then((msg) => { console.assert(msg == "success", msg) })
A0_STATIC_INLINE
void rest_pub(uWS::HttpResponse<false>* res,
              uWS::HttpRequest* req) {
  rest_common(res, req, [res](const RequestMessage& req_msg) {
    // Check required fields.
    req_msg.require("topic");
    req_msg.require(nlohmann::json::json_pointer("/packet/payload"));

    // Perform requested action.
    Publisher p(req_msg.topic);
    p.pub(std::move(req_msg.pkt));

    rest_respond(res, "200", {}, "success");
  });
}

}  // namespace a0::api
