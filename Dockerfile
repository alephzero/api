###########
# Builder #
###########

FROM ubuntu:20.04 as builder

RUN apt update && DEBIAN_FRONTEND="noninteractive" apt install -y \
    g++ git make wget zlib1g-dev

RUN mkdir -p /alephzero && \
    cd /alephzero && \
    git clone -b v0.3 --recurse-submodules https://github.com/alephzero/alephzero.git && \
    cd /alephzero/alephzero && \
    make install -j

RUN mkdir -p /uNetworking && \
    cd /uNetworking && \
    git clone --depth 1 --branch v0.7.1 https://github.com/uNetworking/uSockets.git && \
    git clone --depth 1 --branch v18.23.0  https://github.com/uNetworking/uWebSockets.git && \
    cd /uNetworking/uSockets && \
    make -j && \
    mv /uNetworking/uSockets/uSockets.a /uNetworking/uSockets/libuSockets.a

RUN mkdir -p /nlohmann && \
    cd /nlohmann && \
    wget https://github.com/nlohmann/json/releases/download/v3.9.1/json.hpp

WORKDIR /
COPY include /include
COPY api.cpp /api.cpp

# Move the following into a Makefile
ARG mode=opt
RUN g++ \
    -o /api.bin \
    -std=c++17 \
    $([ "$mode" = "opt" ] && echo "-O3 -flto") \
    $([ "$mode" = "dbg" ] && echo "-O0 -g3") \
    $([ "$mode" = "cov" ] && echo "-O0 -g3 -fprofile-arcs -ftest-coverage --coverage") \
    -I/ \
    -I/include \
    -I/uNetworking/uSockets/src \
    -I/uNetworking/uWebSockets/src \
    /api.cpp \
    -L/lib \
    -L/uNetworking/uSockets \
    -Wl,-Bstatic \
    -lz \
    -lalephzero \
    -luSockets \
    -Wl,-Bdynamic \
    -lpthread

##########
# Deploy #
##########

FROM ubuntu:20.04

COPY --from=builder /api.bin /

ENTRYPOINT ["/api.bin"]
