###########
# Builder #
###########

FROM alpine:3.10 as builder

RUN apk add --no-cache g++ git linux-headers make python3-dev

RUN mkdir -p /alephzero && \
    cd /alephzero && \
    git clone https://github.com/alephzero/alephzero.git && \
    cd /alephzero/alephzero && \
    git reset --hard 7d965d584e9647daf7399ef6253635b289491a0b && \
    make install -j

RUN cd /alephzero && \
    git clone https://github.com/alephzero/py.git && \
    cd /alephzero/py && \
    git reset --hard f3dfbf44a1e9bd41309936a29db9a818321e536a && \
    pip3 install -r requirements.txt && \
    python3 setup.py install

##########
# Deploy #
##########

FROM alpine:3.10

RUN apk add --no-cache libstdc++ python3

RUN pip3 install aiohttp aiohttp_cors && \
    rm -rf /root/.cache/pip/*

COPY --from=builder /usr/include/a0 /usr/include/a0
COPY --from=builder /usr/include/alephzero.h /usr/include/alephzero.h
COPY --from=builder /usr/lib/libalephzero.* /usr/lib/
COPY --from=builder /usr/lib/python3.7/site-packages/alephzero.* /usr/lib/python3.7/site-packages/
COPY entrypoint.py /entrypoint.py

ENTRYPOINT ["/entrypoint.py"]
