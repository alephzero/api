#pragma once

#include <string>
#include <string_view>
#include <vector>

namespace a0::api {

struct strutil {
  template <typename... Arg>
  static std::string cat(Arg&&... arg) {
    std::ostringstream ss;
    (void)(ss << ... << std::forward<Arg>(arg));
    return ss.str();
  }

  template <typename Container>
  static std::string join(Container c) {
    std::ostringstream ss;
    for (auto&& v : c) {
      ss << v;
    }
    return ss.str();
  }

  template <typename... Args>
  static std::string fmt(std::string_view format, Args... args) {
    size_t size = snprintf(nullptr, 0, format.data(), args...);
    std::vector<char> buf(size + 1);
    sprintf(buf.data(), format.data(), args...);
    return std::string(buf.data(), size);
  }

  static std::vector<std::string_view> split(std::string_view str,
                                             std::string_view delim) {
    std::vector<std::string_view> parts;
    size_t last = 0;
    size_t next = 0;
    while ((next = str.find(delim, last)) != std::string::npos) {
      parts.push_back(str.substr(last, next - last));
      last = next + delim.size();
    }
    parts.push_back(str.substr(last));
    return parts;
  }

  static bool endswith(std::string_view str, std::string_view suffix) {
    return str.size() >= suffix.size() &&
           str.compare(str.size() - suffix.size(), suffix.size(), suffix) == 0;
  }

  static void log(std::string_view str) {
    a0_time_wall_t now;
    a0_time_wall_now(&now);

    char now_str[36];
    a0_time_wall_str(now, now_str);

    fprintf(stderr, "%s] %.*s\n", now_str, (int)str.size(), str.data());
  }

  static std::vector<std::pair<std::string, std::string>> flatten(
      std::unordered_multimap<std::string, std::string> mm) {
    std::vector<std::pair<std::string, std::string>> result;
    for (auto&& [k, v] : mm) {
      result.push_back({std::move(k), std::move(v)});
    }
    return result;
  }

  static std::vector<std::pair<std::string, std::string>> flatten_headers(a0_flat_packet_t fpkt) {
    std::vector<std::pair<std::string, std::string>> hdrs;

    a0_flat_packet_header_iterator_t iter;
    a0_packet_header_t hdr;

    a0_flat_packet_header_iterator_init(&iter, &fpkt);
    while (a0_flat_packet_header_iterator_next(&iter, &hdr) == A0_OK) {
      hdrs.push_back({std::string(hdr.key), std::string(hdr.val)});
    }

    return hdrs;
  }
};

}  // namespace a0::api
