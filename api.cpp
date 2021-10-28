#include <App.h>
#include <a0.h>

#include "a0/api/actions/rest_ls.hpp"
#include "a0/api/actions/rest_pub.hpp"
#include "a0/api/actions/rest_rpc.hpp"
#include "a0/api/actions/rest_write.hpp"
#include "a0/api/actions/ws_log.hpp"
#include "a0/api/actions/ws_prpc.hpp"
#include "a0/api/actions/ws_read.hpp"
#include "a0/api/actions/ws_sub.hpp"
#include "a0/api/global_state.hpp"

// TODO(lshamis): The following decisions were made for backwards compatability.
// * /wsapi/* is a weird path name.
// * API version isn't part of the path: /api/v2/...?

int main() {
  auto API_READY_TOPIC = std::string(a0::api::env("API_READY_TOPIC", "api_ready"));
  auto PORT_STR = a0::api::env("PORT_STR", "24880");

  int PORT;
  try {
    PORT = std::stoi(PORT_STR.data());
  } catch (const std::exception& err) {
    fprintf(stderr, "Invalid port requested: %s\n", err.what());
    return -1;
  }

  uWS::App app;
  app.get("/api/ls", a0::api::rest_ls);
  app.post("/api/pub", a0::api::rest_pub);
  app.post("/api/rpc", a0::api::rest_rpc);
  app.post("/api/write", a0::api::rest_write);
  app.ws<a0::api::WSLog::Data>("/wsapi/log", a0::api::WSLog::behavior());
  app.ws<a0::api::WSRead::Data>("/wsapi/read", a0::api::WSRead::behavior());
  app.ws<a0::api::WSSub::Data>("/wsapi/sub", a0::api::WSSub::behavior());
  app.ws<a0::api::WSPrpc::Data>("/wsapi/prpc", a0::api::WSPrpc::behavior());
  app.listen(PORT, [&](auto* socket) {
    a0::api::global()->listen_socket = socket;
    a0::Publisher(API_READY_TOPIC).pub("ready");
  });

  a0::api::global()->event_loop = uWS::Loop::get();
  a0::api::global()->running = true;
  a0::api::attach_signal_handler();

  app.run();
}
