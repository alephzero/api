#pragma once

#include <a0.h>
#include <nlohmann/json.hpp>

#include <string>

#include "a0/api/encoders.hpp"
#include "a0/api/strutil.hpp"

namespace a0::api {

struct RequestMessage {
  // Original client message.
  nlohmann::json raw_msg;
  // Commonly requested fields.
  std::string path;
  std::string topic;
  a0::Packet pkt;
  std::function<std::string(std::string_view)> response_encoder;

  template <typename FieldT>
  void require(const FieldT& field) const {
    if (!raw_msg.contains(field)) {
      throw std::invalid_argument(
          strutil::cat("Request missing required field: ", field));
    }
  }

  template <typename T, typename FieldT>
  void require_get_to(const FieldT& field, T& out) const {
    require(field);
    try {
      raw_msg.at(field).get_to(out);
    } catch (std::exception& e) {
      throw std::invalid_argument(
          strutil::cat("Request field has incorrect format. field: ", field,
                       "  error: ", e.what()));
    }
  }

  template <typename T, typename FieldT>
  T require_get(const FieldT& field) const {
    T out;
    require_get_to(field, out);
    return out;
  }

  template <typename T, typename FieldT>
  void maybe_get_to(const FieldT& field, T& out) const {
    if (!raw_msg.contains(field)) {
      return;
    }
    try {
      raw_msg.at(field).get_to(out);
    } catch (std::exception& e) {
      throw std::invalid_argument(
          strutil::cat("Request field has incorrect format. field: ", field,
                       "  error: ", e.what()));
    }
  }

  template <typename T, typename FieldT>
  T maybe_get(const FieldT& field) const {
    T out;
    maybe_get_to(field, out);
    return out;
  }

  template <typename T, typename FieldT>
  void require_option_to(const FieldT& field,
                         const std::unordered_map<std::string, T>& option_map,
                         T& out) const {
    std::string option;
    require_get_to(field, option);
    if (!option_map.count(option)) {
      throw std::invalid_argument(strutil::cat(
          "Request has unknown value for field: ", field, "  value: ", option));
    }
    out = option_map.at(option);
  }

  template <typename T, typename FieldT>
  T require_option(const FieldT& field,
                   const std::unordered_map<std::string, T>& option_map) const {
    T out;
    require_option_to(field, option_map, out);
    return out;
  }

  template <typename T, typename FieldT>
  void maybe_option_to(const FieldT& field,
                       const std::unordered_map<std::string, T>& option_map,
                       T& out) const {
    std::string option;
    maybe_get_to(field, option);
    if (option.empty()) {
      return;
    }
    if (!option_map.count(option)) {
      throw std::invalid_argument(strutil::cat(
          "Request has unknown value for field: ", field, "  value: ", option));
    }
    out = option_map.at(option);
  }

  template <typename T, typename FieldT>
  T maybe_option(const FieldT& field,
                 const std::unordered_map<std::string, T>& option_map) const {
    T out;
    maybe_option_to(field, option_map, out);
    return out;
  }
};

static inline RequestMessage ParseRequestMessage(std::string_view str) {
  RequestMessage msg;

  // Check input is JSON.
  msg.raw_msg = nlohmann::json::parse(str, nullptr, false);
  if (msg.raw_msg.is_discarded()) {
    throw std::invalid_argument("Request must be json.");
  }

  // Check input is an object.
  if (!msg.raw_msg.is_object()) {
    throw std::invalid_argument("Request must be a json object.");
  }

  // Check for common fields.
  msg.maybe_get_to("path", msg.path);
  msg.maybe_get_to("topic", msg.topic);

  // Extract packet fields.
  auto headers_list =
      msg.maybe_get<std::vector<std::pair<std::string, std::string>>>(
          nlohmann::json::json_pointer("/packet/headers"));
  std::unordered_multimap<std::string, std::string> headers;
  for (const auto& header : headers_list) {
    headers.insert({std::move(header.first), std::move(header.second)});
  }
  auto payload = msg.maybe_get<std::string>(
      nlohmann::json::json_pointer("/packet/payload"));

  // Extract encodings.
  auto decoder = Decoders().at("");
  msg.maybe_option_to("request_encoding", Decoders(), decoder);
  if (decoder) {
    payload = decoder(std::move(payload));
  }
  msg.response_encoder = Encoders().at("");
  msg.maybe_option_to("response_encoding", Encoders(), msg.response_encoder);

  // Compose the packet.
  msg.pkt = a0::Packet(std::move(headers), std::move(payload));

  return msg;
}

}  // namespace a0::api
