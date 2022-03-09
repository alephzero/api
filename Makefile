BIN_DIR = bin

CXXFLAGS += -std=c++17
CXXFLAGS += -Iinclude
CXXFLAGS += -Ithird_party/alephzero/alephzero/include
CXXFLAGS += -Ithird_party/alephzero/alephzero/third_party/yyjson/src/
CXXFLAGS += -Ithird_party/alephzero/alephzero/third_party/json/single_include/
CXXFLAGS += -Ithird_party/uNetworking/uWebSockets/src
CXXFLAGS += -Ithird_party/uNetworking/uWebSockets/uSockets/src

LDFLAGS += -Lthird_party/alephzero/alephzero/lib/
LDFLAGS += -Lthird_party/uNetworking/uWebSockets/uSockets
LDFLAGS += -static-libstdc++ -static-libgcc
LDFLAGS += -Wl,-Bstatic -lz -lalephzero -l:uSockets.a -Wl,-Bdynamic
LDFLAGS += -lpthread

DEBUG ?= 0
ifeq ($(DEBUG), 1)
	CXXFLAGS += -O0 -g3 -ggdb3 -DDEBUG
else
	CXXFLAGS += -O2 -flto -DNDEBUG
endif

$(BIN_DIR)/api: api.cpp
	@mkdir -p $(@D)
	$(MAKE) -C third_party/alephzero/alephzero lib/libalephzero.a
	$(MAKE) -C third_party/uNetworking/uWebSockets/uSockets
	$(CXX) -o $@ $(CXXFLAGS) $< $(LDFLAGS)

.PHONY: run
run: $(BIN_DIR)/api
	$(BIN_DIR)/api

.PHONY: clean
clean:
	$(MAKE) -C third_party/alephzero/alephzero clean
	$(MAKE) -C third_party/uNetworking/uWebSockets/uSockets clean
	rm -rf $(BIN_DIR)
