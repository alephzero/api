FROM ubuntu:20.04

RUN apt update && DEBIAN_FRONTEND="noninteractive" apt install -y \
    git python3-dev python3-pip valgrind
RUN python3 -m pip install -U \
    pip \
    wheel \
    setuptools \
    pytest \
    pytest-asyncio \
    requests \
    websockets==9.1

RUN mkdir /alephzero &&                                      \
    cd /alephzero &&                                         \
    git clone -b dev --recurse-submodules https://github.com/alephzero/py.git &&         \
    cd /alephzero/py &&                                      \
    python3 -m pip install .

COPY --from=alephzero_api /api.bin /
COPY ./test /test
ENTRYPOINT ["python3", "-m", "pytest", "/test/test_api.py"]
