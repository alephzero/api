#pragma once

#include <string>
#include <string_view>
#include <vector>

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

  static void log(std::string_view str) {
    timespec now;
    a0_time_wall_now(&now);

    char now_str[36];
    a0_time_wall_str(now, now_str);

    fprintf(stderr, "%s] %.*s\n", now_str, (int)str.size(), str.data());
  }
};
