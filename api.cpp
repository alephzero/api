#include <App.h>
#include <a0.h>

#include "a0/bridge/bridge.hpp"
#include "a0/bridge/plugin/alephzero.hpp"
#include "a0/bridge/plugin/tcp.hpp"

#include "a0/web/actions/rest_ls.hpp"
#include "a0/web/actions/rest_pub.hpp"
#include "a0/web/actions/rest_rpc.hpp"
#include "a0/web/actions/ws_prpc.hpp"
#include "a0/web/actions/ws_sub.hpp"
#include "a0/web/global_state.hpp"

// TODO(lshamis): The following decisions were made for backwards compatability.
// * /wsapi/* is a weird path name.
// * API version isn't part of the path: /api/v2/...?

// int main() {
//   auto API_READY_TOPIC = std::string(a0::api::env("API_READY_TOPIC", "api_ready"));
//   auto PORT_STR = a0::api::env("PORT_STR", "24880");

//   int PORT;
//   try {
//     PORT = std::stoi(PORT_STR.data());
//   } catch (const std::exception& err) {
//     fprintf(stderr, "Invalid port requested: %s\n", err.what());
//     return -1;
//   }

//   uWS::App app;
//   app.get("/api/ls", a0::api::rest_ls);
//   app.post("/api/pub", a0::api::rest_pub);
//   app.post("/api/rpc", a0::api::rest_rpc);
//   app.ws<a0::api::WSSub::Data>("/wsapi/sub", a0::api::WSSub::behavior());
//   app.ws<a0::api::WSPrpc::Data>("/wsapi/prpc", a0::api::WSPrpc::behavior());
//   app.listen(PORT, [&](auto* socket) {
//     a0::api::global()->listen_socket = socket;
//     a0::Publisher(API_READY_TOPIC).pub("ready");
//   });

//   a0::api::global()->event_loop = uWS::Loop::get();
//   a0::api::global()->running = true;
//   a0::api::attach_signal_handler();

//   app.run();
// }


int main() {
  std::atomic<int> cnt(0);

  asio::io_context io;
  asio::io_context::strand strand_(io);

  std::vector<std::thread> ts;
  for (int i = 0; i < 30; i++) {
    ts.push_back(std::thread([&]() {
      for (int j = 0; j < 100000; j++) {
        strand_.post([&]() { cnt++; });  // works
        // asio::post([&]() { cnt++; });  // not working
      }
    }));
  }

  std::cout << "all running" << std::endl;
  for (auto& t : ts) t.join();

  std::thread iot([&]() { io.run(); });
  std::cout << "ts joined" << std::endl;
  iot.join();
  std::cout << "iot joined" << std::endl;

  std::cout << cnt << std::endl;

  return 0;
}
