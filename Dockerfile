###########
# Builder #
###########

FROM ubuntu:20.04 as builder

RUN apt update && DEBIAN_FRONTEND="noninteractive" apt install -y \
    g++ git make wget zlib1g-dev

WORKDIR /workdir
COPY . /workdir

RUN make clean && make bin/api -j

##########
# Deploy #
##########

FROM busybox:glibc

COPY --from=builder /workdir/bin/api /api.bin

ENTRYPOINT ["/api.bin"]
