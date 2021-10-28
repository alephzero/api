#!/bin/bash
cd "$(dirname "$0")"

docker build -t alephzero/api .

# TODO(lshamis): Take ipc container as arg.

docker run \
    --rm -it \
    --name=a0_api \
    --ipc=host \
    --pid=host \
    -p 24880:24880 \
    alephzero/api
