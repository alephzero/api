#pragma once

#include <asio.hpp>

namespace a0::api {

a0_alloc_t malloc_allocator() {
  return a0_alloc_t{
    .alloc = [](void*, size_t size, a0_buf_t* out) {
      *out = {(uint8_t*)malloc(size), size};
      return A0_OK;
    },
  };
}

class TcpSource : public Source::Base {
  Sink sink;

  std::string host;
  std::string port;

  asio::io_context io;
  asio::ip::tcp::socket sock;

  uint64_t backoff{0};
  uint64_t next_pkt_len;
  std::vector<uint8_t> next_pkt;

  std::thread t;

 public:
  TcpSource(nlohmann::json args, Sink sink) : sink(std::move(sink)), sock(io) {
    args.at("host").get_to(host);
    args.at("port").get_to(port);

    do_connect();

    t = std::thread([this]() {
      io.run();
    });
  }

 private:
  void do_connect() {
    asio::async_connect(
        sock,
        asio::ip::tcp::resolver(io).resolve(host, port),
        [this](std::error_code err, asio::ip::tcp::endpoint) {
      if (err) {
        std::cerr << "connect error: " << err.message() << std::endl;
        backoff++;
        do_connect_later();
        return;
      }
      
      backoff = 0;
      do_read_pkt_len();
    });
  }

  void do_connect_later() {
    asio::steady_timer timer(io, std::chrono::milliseconds(std::min<uint64_t>(5000, std::pow(2, backoff))));
    timer.async_wait([this](std::error_code err) {
      if (err) {
        std::cerr << "timer error: " << err.message() << std::endl;
      }
      do_connect();
    });
  }

  void do_read_pkt_len() {
    asio::async_read(
        sock,
        asio::buffer(&next_pkt_len, sizeof(next_pkt_len)),
        [this](std::error_code err, size_t size) {
          if (err) {
            on_read_err(err);
            return;
          }

          do_read_pkt();
        });
  }

  void do_read_pkt() {
    next_pkt.resize(next_pkt_len);
    asio::async_read(
        sock,
        asio::buffer(next_pkt),
        [this](std::error_code err, size_t) {
          if (err) {
            on_read_err(err);
            return;
          }

          a0_flat_packet_t fpkt{{next_pkt.data(), next_pkt.size()}};
          a0_packet_t pkt;
          a0_buf_t pkt_buf;
          a0_packet_deserialize(fpkt, malloc_allocator(), &pkt, &pkt_buf);

          sink(Packet(pkt, [&](a0_packet_t*) {
            free(pkt_buf.data);
          }));

          do_read_pkt_len();
        });
  }

  void on_read_err(std::error_code err) {
    std::cerr << "read error: " << err.message() << std::endl;
    sock.close();
    do_connect();
    return;
  }
};

REGISTER_SOURCE(tcp, TcpSource);

class TcpSink : public Sink::Base {
  int port;

  asio::io_context io;
  std::unique_ptr<asio::ip::tcp::acceptor> acceptor;
  std::map<uint64_t, std::unique_ptr<asio::ip::tcp::socket>> sockets;
  uint64_t next_sock_id{0};

 public:
  TcpSink(nlohmann::json args) {
    args.at("port").get_to(port);

    asio::ip::tcp::endpoint endpoint(asio::ip::tcp::v4(), port);
    acceptor = std::make_unique<asio::ip::tcp::acceptor>(io, endpoint);
  }

  void do_accept() {
    acceptor->async_accept(
        [this](std::error_code err, asio::ip::tcp::socket sock) {
          if (err) {
            std::cerr << "accept error: " << err.message() << std::endl;
          } else {
            // std::make_shared<chat_session>(std::move(sock), room_)->start();
            sockets.emplace(next_sock_id++, std::make_unique<asio::ip::tcp::socket>(std::move(sock)));
          }

          do_accept();
        });
  }

  void operator()(Packet pkt) override {
    a0_flat_packet_t fpkt;
    a0_packet_serialize(*pkt.c, malloc_allocator(), &fpkt);

    for (auto& [id, sock] : sockets) {
      // asio::error_code err;
      // asio::write(*sock, asio::buffer(fpkt.buf.data, fpkt.buf.size), &err);
      
      // asio::async_write(
      //     *sock,
      //     asio::buffer(fpkt.buf.data, fpkt.buf.size),
      //     [this, id](std::error_code err, size_t) mutable {
      //       if (!sockets.count(id)) {
      //         return;
      //       }
      //       if (err) {
      //         std::cerr << "write error to " << sockets[id]->remote_endpoint().address().to_string() << ": " << err.message() << std::endl;
      //         sockets.erase(id);
      //       }
      //     });
    }

    free(fpkt.buf.data);
    // asio::async_write();
    // asio::write(s, asio::buffer(request, request_length));
  }
};

REGISTER_SINK(tcp, TcpSink);

}  // namespace a0::api
