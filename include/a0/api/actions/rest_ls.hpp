#pragma once

#include <App.h>
#include <nlohmann/json.hpp>

#include <filesystem>

#include "a0/api/env.hpp"
#include "a0/api/rest_helpers.hpp"
#include "a0/api/strutil.hpp"

namespace a0::api {

// fetch(`http://${api_addr}/api/ls`)
// .then((r) => { return r.text() })
// .then((msg) => { console.log(msg) })
static inline void rest_ls(uWS::HttpResponse<false>* res,
                           uWS::HttpRequest* req) {
  std::vector<std::string> out;
  // Scan the root directory recursively for files ending with ".a0".
  for (auto&& entry : std::filesystem::recursive_directory_iterator(env::root())) {
    auto path = std::string(std::filesystem::relative(entry.path(), env::root()));
    if (strutil::endswith(path, ".a0")) {
      out.push_back(path);
    }
  }
  std::sort(out.begin(), out.end());

  rest_respond(res, "200", {}, nlohmann::json(out).dump());
}

}  // namespace a0::api
