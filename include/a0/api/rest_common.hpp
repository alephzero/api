#pragma once

#include <App.h>

#include <functional>
#include <string_view>

#include "a0/api/request_message.hpp"

namespace a0::api {

static inline void rest_respond(uWS::HttpResponse<false>* res,
                                std::string_view status,
                                std::vector<std::pair<std::string, std::string>> headers,
                                std::string_view body) {
  headers.push_back({"Access-Control-Allow-Origin", "*"});

  res->writeStatus(status);
  for (auto&& [key, val] : headers) {
    res->writeHeader(key, val);
  }
  res->end(body);
}

static inline void rest_common(
    uWS::HttpResponse<false>* res,
    uWS::HttpRequest* req,
    std::function<void(const RequestMessage&)> impl) {
  res->onData([res, impl, ss = std::stringstream()](std::string_view chunk, bool is_end) mutable {
    ss << chunk;
    if (!is_end) {
      return;
    }

    try {
      impl(ParseRequestMessage(ss.str()));
    } catch (std::exception& e) {
      rest_respond(res, "400", {}, e.what());
    }
  });

  res->onAborted([]() {});
}

}  // namespace a0::api
