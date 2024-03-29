#!/bin/bash
cd "$(dirname "$0")"

rm /tmp/alephzero_ci.Dockerfile
cat <<EOF >> /tmp/alephzero_ci.Dockerfile
FROM alpine:latest

RUN apk add --no-cache bash

RUN wget https://raw.githubusercontent.com/nektos/act/master/install.sh
RUN bash install.sh v0.2.23
EOF

docker build -t alephzero_ci . -f /tmp/alephzero_ci.Dockerfile

docker run \
  --rm -it \
  -v ${PWD}:/alephzero \
  -w /alephzero \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /usr/bin/docker:/usr/bin/docker \
  alephzero_ci act $@
