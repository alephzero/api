#pragma once

#include <App.h>
#include <a0.h>

#include <sstream>

#include "a0/api/request_message.hpp"
#include "a0/api/rest_common.hpp"

namespace a0::api {

// fetch(`http://${api_addr}/api/write`, {
//     method: "POST",
//     body: JSON.stringify({
//         path: "...",                      // required
//         standard_headers: false,          // optional
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
void rest_write(uWS::HttpResponse<false>* res,
                uWS::HttpRequest* req) {
  rest_common(res, req, [res](const RequestMessage& req_msg) {
    // Check required fields.
    req_msg.require("path");
    req_msg.require(nlohmann::json::json_pointer("/packet/payload"));
    bool standard_headers = false;
    req_msg.maybe_get_to("standard_headers", standard_headers);

    // Perform requested action.
    Writer w(File(req_msg.path));
    if (standard_headers) {
      w.push(add_standard_headers());
    }
    w.write(std::move(req_msg.pkt));

    rest_respond(res, "200", {}, "success");
  });
}

}  // namespace a0::api
