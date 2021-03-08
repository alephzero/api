#pragma once

#include <App.h>
#include <nlohmann/json.hpp>

#include <filesystem>

#include "src/env.hpp"
#include "src/rest_helpers.hpp"
#include "src/strutil.hpp"

// fetch(`http://${api_addr}/api/ls`)
// .then((r) => { return r.text() })
// .then((msg) => { console.log(msg) })
static inline void rest_ls(uWS::HttpResponse<false>* res,
                           uWS::HttpRequest* req) {
  auto root = env("A0_ROOT", "/dev/shm");

  nlohmann::json out;
  // Scan the root directory for files starting with "a0_".
  // Files are expected to have the format:
  // "a0_{protocol}__{container}__{topic}". {container} and {topic} are
  // optional.
  for (auto&& entry : std::filesystem::directory_iterator(root)) {
    std::string filename = entry.path().filename();
    if (filename.rfind("a0_", 0) != 0) {
      continue;
    }

    auto parts = strutil::split(filename, "__");
    nlohmann::json jentry = {
        {"filename", filename},
        {"protocol", parts[0].substr(3)},
    };
    if (parts.size() > 1) {
      jentry["container"] = parts[1];
    }
    if (parts.size() > 2) {
      jentry["topic"] = parts[2];
    }

    out.push_back(std::move(jentry));
  }
  std::sort(out.begin(), out.end(), [](const auto& lhs, const auto& rhs) {
    return lhs.at("filename") < rhs.at("filename");
  });

  rest_respond(res, "200", {}, out.dump());
}