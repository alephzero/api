#include <App.h>
#include <a0.h>

#include "src/actions/rest_ls.hpp"
#include "src/actions/rest_pub.hpp"
#include "src/actions/rest_rpc.hpp"
#include "src/actions/ws_prpc.hpp"
#include "src/actions/ws_pub.hpp"
#include "src/actions/ws_sub.hpp"
#include "src/global_state.hpp"

// TODO(lshamis): The following decisions were made for backwards compatability.
// * (En/De)coding defaults to base64. Should default to none.
// * Does /wsapi/pub make sense to keep?
// * /wsapi/* is a weird path name.
// * API version isn't part of the path: /api/v2/...?

int main() {
  auto CONTAINER = a0::api::env("CONTAINER", "api");
  auto PORT_STR = a0::api::env("PORT_STR", "24880");

  int PORT;
  try {
    PORT = std::stoi(PORT_STR.data());
  } catch (const std::exception& err) {
    fprintf(stderr, "Invalid port requested: %s\n", err.what());
    return -1;
  }

  // Used to name the heartbeat.
  a0::InitGlobalTopicManager({
      .container = CONTAINER.data(),
      .subscriber_aliases = {},
      .rpc_client_aliases = {},
      .prpc_client_aliases = {},
  });

  uWS::App app;
  app.get("/api/ls", a0::api::rest_ls);
  app.post("/api/pub", a0::api::rest_pub);
  app.post("/api/rpc", a0::api::rest_rpc);
  app.ws<a0::api::WSPub::Data>("/wsapi/pub", a0::api::WSPub::behavior());
  app.ws<a0::api::WSSub::Data>("/wsapi/sub", a0::api::WSSub::behavior());
  app.ws<a0::api::WSPrpc::Data>("/wsapi/prpc", a0::api::WSPrpc::behavior());
  app.listen(PORT, [&](auto* socket) {
    a0::api::global()->listen_socket = socket;
    a0::api::global()->heartbeat = std::make_unique<a0::Heartbeat>();
  });

  a0::api::global()->event_loop = uWS::Loop::get();
  a0::api::global()->running = true;
  a0::api::attach_signal_handler();

  app.run();
}
