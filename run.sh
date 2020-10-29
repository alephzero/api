#!/bin/bash
cd "$(dirname "$0")"

docker build -t alephzero_api .

# TODO(lshamis): Take ipc container as arg.

docker run --rm -it --name=a0_api --ipc=host -p 24880:24880 alephzero_api
