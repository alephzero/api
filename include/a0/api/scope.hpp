#pragma once

#include <functional>
#include <memory>

namespace a0::api {

std::shared_ptr<void> scope_guard(std::function<void()> fn) {
  return std::shared_ptr<void>((void*)1, [fn](void*) { fn(); });
}

std::shared_ptr<void> scope_unlock_transport(a0_transport_locked_t tlk) {
  a0_transport_unlock(tlk);
  return scope_guard([tlk]() {
    a0_transport_locked_t unused;
    a0_transport_lock(tlk.transport, &unused);
  });
}

}  // namespace a0::api
