#pragma once

#include <App.h>

#include <sstream>

#include "src/request_message.hpp"
#include "src/rest_helpers.hpp"

namespace a0::api {

// fetch(`http://${api_addr}/api/pub`, {
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
//     })
// })
// .then((r) => { return r.text() })
// .then((msg) => { console.assert(msg == "success", msg) })
static inline void rest_pub(uWS::HttpResponse<false>* res,
                            uWS::HttpRequest* req) {
  res->onData([res, ss = std::stringstream()](std::string_view chunk, bool is_end) mutable {
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
    tm.container = req_msg.container;
    auto topic = tm.publisher_topic(req_msg.topic);

    // Perform requested action.
    a0::Publisher p(topic);
    p.pub(std::move(req_msg.pkt));

    rest_respond(res, "200", {}, "success");
  });

  res->onAborted([]() {});
}

}  // namespace a0::api
