#!/bin/bash
set -e
cd "$(dirname "$0")"

docker build \
    -t alephzero/api:cov \
    --build-arg=mode=cov \
    -f ../Dockerfile \
    ..

docker build \
    -t alephzero/api_test \
    -f ./Dockerfile \
    ..

docker run \
    --rm \
    -it \
    --pid=host \
    --ipc=host \
    alephzero/api_test
