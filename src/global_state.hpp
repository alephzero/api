#pragma once

#include <App.h>
#include <signal.h>

struct GlobalState {
  uWS::Loop* event_loop;
  // The following can be used anywhere.
  std::atomic<bool> running;
  // The following should only be used within the event_loop.
  us_listen_socket_t* listen_socket;
  std::set<uWS::WebSocket<false, true>*> active_ws;
  std::unique_ptr<a0::Heartbeat> heartbeat;
  // The following should only be used to lock alephzero threads.
  std::mutex mu;
  std::condition_variable cv;

  static GlobalState* get() {
    static GlobalState state;
    return &state;
  }

 private:
  GlobalState() = default;
};

GlobalState* global() {
  return GlobalState::get();
}

void shutdown() {
  global()->running = false;
  global()->event_loop->defer([]() {
    if (global()->listen_socket) {
      us_listen_socket_close(0, global()->listen_socket);
      global()->listen_socket = nullptr;
    }
    for (auto* ws : global()->active_ws) {
      ws->close();
    }
  });
}

void attach_signal_handler() {
  static struct sigaction sigact;

  memset(&sigact, 0, sizeof(sigact));
  sigact.sa_sigaction = [](int sig, siginfo_t*, void*) { shutdown(); };
  sigact.sa_flags = SA_SIGINFO;

  sigaction(SIGTERM, &sigact, NULL);
  sigaction(SIGINT, &sigact, NULL);
}