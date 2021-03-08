#pragma once

#include <App.h>

#include <string_view>

void rest_respond(uWS::HttpResponse<false>* res,
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
