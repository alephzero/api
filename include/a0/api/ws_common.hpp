#pragma once

namespace a0::api {

// Accessed from all threads.
struct WSCommon : std::enable_shared_from_this<WSCommon> {
  scheduler_t sched{scheduler_t::ON_DRAIN};

  uint64_t reader_seq_min{0};
  Reader::Init reader_init{Reader::Init::AWAIT_NEW};
  Reader::Iter reader_iter{Reader::Iter::NEXT};

  std::atomic<int64_t> wake_cnt{0};
  std::function<void()> wake_hook;
  bool init{false};
  std::atomic<bool> done{false};

  template <typename WebSocket>
  void OnMessageWithHandshake(
      WebSocket* ws,
      std::string_view msg,
      uWS::OpCode code,
      std::function<void(const RequestMessage&)> onhandshake) {
    if (code != uWS::OpCode::TEXT) {
      return;
    }

    if (!init) {
      // Parse the request, including common fields.
      try {
        auto req_msg = ParseRequestMessage(msg);
        LoadCommonOptions(req_msg);
        onhandshake(req_msg);
      } catch (std::exception& e) {
        ws->end(4000, e.what());
        return;
      }

      init = true;
      return;
    }

    // If the handshake is complete, and scheduler is ON_ACK, and message is "ACK", unblock the next message.
    if (sched == scheduler_t::ON_ACK && msg == std::string_view("ACK")) {
      wake();
      return;
    }

    // Error. Should not init multiple times!
    ws->end(4000, "Handshake only allowed once per websocket.");
  }

  void LoadCommonOptions(const RequestMessage& req_msg) {
    req_msg.maybe_option_to("scheduler", scheduler_map(), sched),
        req_msg.maybe_option_to("iter", iter_map(), reader_iter);

    // Get the optional 'init' option.
    // It may be an int representing the earliest acceptable sequence number.
    auto init_field = req_msg.raw_msg.find("init");
    if (init_field != req_msg.raw_msg.end()) {
      if (init_field->is_number()) {
        reader_seq_min = init_field->get<int>();
        if (reader_iter == Reader::Iter::NEXT) {
          reader_init = Reader::Init::OLDEST;
        } else if (reader_iter == Reader::Iter::NEWEST) {
          reader_init = Reader::Init::MOST_RECENT;
        }
      } else {
        req_msg.maybe_option_to("init", init_map(), reader_init);
      }
    }
  }

  void wake() {
    wake_cnt++;
    global()->cv.notify_all();
    if (wake_hook) {
      wake_hook();
    }
  }

  void wait(uint64_t pre_send_cnt) {
    if (sched == scheduler_t::IMMEDIATE) {
      return;
    }

    std::unique_lock<std::mutex> lk{global()->mu};
    global()->cv.wait(lk, [this, pre_send_cnt]() {
      // Unblock if:
      // * system is shutting down.
      // * websocket is closing.
      // * the scheduler is ready for the next message.
      return !global()->running || done || pre_send_cnt < wake_cnt;
    });
  }

  template <typename WebSocket>
  void ondrain(WebSocket* ws) {
    if (sched == scheduler_t::ON_DRAIN && ws->getBufferedAmount() == 0) {
      wake();
    }
  }

  template <typename WebSocket>
  void onclose(WebSocket* ws) {
    done = true;
    global()->active_ws.erase(ws);
    global()->cv.notify_all();
  }

  template <typename WebSocket>
  void send(WebSocket* ws, std::string str) {
    // Schedule the event loop to perform the send operation.
    global()->event_loop->defer(
        [self = shared_from_this(), ws, str = std::move(str)]() {
          // Make sure the ws hasn't closed between the reader callback and this task.
          if (!global()->running || !global()->active_ws.count(ws)) {
            return;
          }
          auto send_status = ws->send(std::move(str), uWS::TEXT, true);

          if (self->sched == scheduler_t::ON_DRAIN && send_status == ws->SUCCESS) {
            self->wake();
          }
        });
  }

  template <typename WebSocket>
  std::function<void(std::string)> bind_send(WebSocket* ws) {
    return [self = shared_from_this(), ws](std::string str) {
      self->send(ws, std::move(str));
    };
  }

  template <typename WebSocket>
  void end(WebSocket* ws, int code, std::string str) {
    // Schedule the event loop to perform the end operation.
    global()->event_loop->defer(
        [self = shared_from_this(), ws, code, str = std::move(str)]() {
          // Make sure the ws hasn't closed between the reader callback and this task.
          if (!global()->running || !global()->active_ws.count(ws)) {
            return;
          }
          ws->end(code, std::move(str));
          self->wake();
        });
  }

  template <typename WebSocket>
  std::function<void(int, std::string)> bind_end(WebSocket* ws) {
    return [self = shared_from_this(), ws](int code, std::string str) {
      self->end(ws, code, std::move(str));
    };
  }
};

}  // namespace a0::api
