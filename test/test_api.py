import a0
import asyncio
import base64
import enum
import json
import os
import pytest
import random
import requests
import subprocess
import sys
import tempfile
import threading
import types
import websockets

pytestmark = pytest.mark.asyncio

# TODO(lshamis): Things to test:
# * unclean shutdown.


class RunApi:

    class State(enum.Enum):
        DEAD = 0
        CREATED = 1
        STARTED = 2

    def __init__(self):
        self.api_proc = None

    def start(self):
        assert not self.api_proc

        ns = types.SimpleNamespace()
        ns.state = RunApi.State.CREATED
        ns.state_cv = threading.Condition()

        def check_ready(pkt):
            with ns.state_cv:
                ns.state = RunApi.State.STARTED
                ns.state_cv.notify_all()

        sub = a0.Subscriber("api_ready", a0.INIT_AWAIT_NEW, a0.ITER_NEXT,
                            check_ready)

        self.api_proc = subprocess.Popen(
            [
                "valgrind", "--leak-check=full", "--error-exitcode=125",
                "/api.bin"
            ],
            env=os.environ.copy(),
        )

        with ns.state_cv:
            assert ns.state_cv.wait_for(
                lambda: ns.state == RunApi.State.STARTED, timeout=10)

    def shutdown(self):
        assert self.api_proc
        self.api_proc.terminate()
        assert self.api_proc.wait() == 0
        self.api_proc = None


@pytest.fixture()
def sandbox():
    tmp_dir = tempfile.TemporaryDirectory(prefix="/dev/shm/")
    os.environ["A0_ROOT"] = tmp_dir.name
    os.environ["PORT_STR"] = str(random.randint(49152, 65535))
    api = RunApi()
    api.start()
    yield api
    api.shutdown()


def btoa(s):
    return base64.b64encode(s.encode("utf-8")).decode("utf-8")


def atob(b):
    return base64.b64decode(b.encode("utf-8")).decode("utf-8")


def test_ls(sandbox):
    resp = requests.get(f"http://localhost:{os.environ['PORT_STR']}/api/ls")

    assert resp.status_code == 200
    assert resp.headers["Access-Control-Allow-Origin"] == "*"
    assert resp.json() == ["alephzero/api_ready.pubsub.a0"]

    a0.File("aaa/bbb.pubsub.a0")
    a0.File("aaa/ccc.pubsub.a0")
    a0.File("bbb/ddd.rpc.a0")

    resp = requests.get(f"http://localhost:{os.environ['PORT_STR']}/api/ls")
    assert resp.status_code == 200
    assert resp.json() == [
        "aaa/bbb.pubsub.a0",
        "aaa/ccc.pubsub.a0",
        "alephzero/api_ready.pubsub.a0",
        "bbb/ddd.rpc.a0",
    ]


def test_pub(sandbox):
    endpoint = f"http://localhost:{os.environ['PORT_STR']}/api/pub"
    pub_data = {
        "topic": "mytopic",
        "packet": {
            "headers": [
                ["xyz", "123"],
                ["zzz", "www"],
            ],
            "payload": "Hello, World!",
        },
    }

    # Normal publish.
    resp = requests.post(endpoint, data=json.dumps(pub_data))
    assert resp.status_code == 200
    assert resp.text == "success"

    # Base64 request_encoding.
    pub_data["request_encoding"] = "base64"
    pub_data["packet"]["payload"] = btoa("Goodbye, World!")
    resp = requests.post(endpoint, data=json.dumps(pub_data))
    assert resp.status_code == 200
    assert resp.text == "success"
    pub_data["packet"]["payload"] = "Hello, World!"
    pub_data.pop("request_encoding")

    # Missing "topic".
    pub_data.pop("topic")
    resp = requests.post(endpoint, data=json.dumps(pub_data))
    assert resp.status_code == 400
    assert resp.text == "Request missing required field: topic"
    pub_data["topic"] = "mytopic"

    # Not JSON.
    resp = requests.post(endpoint, data="not json")
    assert resp.status_code == 400
    assert resp.text == "Request must be json."

    # Not JSON object.
    resp = requests.post(endpoint, data=json.dumps(["not object"]))
    assert resp.status_code == 400
    assert resp.text == "Request must be a json object."

    sub = a0.SubscriberSync("mytopic", a0.INIT_OLDEST, a0.ITER_NEXT)
    hdrs = []
    msgs = []
    while sub.has_next():
        pkt = sub.next()
        hdrs.append(list(pkt.headers))  # Inspect copies of headers.
        msgs.append(pkt.payload)
    assert len(hdrs) == 2
    assert len(msgs) == 2
    assert msgs == [b"Hello, World!", b"Goodbye, World!"]
    for hdr in hdrs:
        for expected in pub_data["packet"]["headers"]:
            hdr.remove(tuple(expected))
        assert sorted([k for k, v in hdr]) == [
            "a0_time_mono",
            "a0_time_wall",
            "a0_transport_seq",
            "a0_writer_id",
            "a0_writer_seq",
        ]


def test_write(sandbox):
    endpoint = f"http://localhost:{os.environ['PORT_STR']}/api/write"
    pub_data = {
        "path": "mypath",
        "packet": {
            "headers": [
                ["xyz", "123"],
                ["zzz", "www"],
            ],
            "payload": "Hello, World!",
        },
    }

    # Normal publish.
    resp = requests.post(endpoint, data=json.dumps(pub_data))
    assert resp.status_code == 200
    assert resp.text == "success"

    # Base64 request_encoding.
    pub_data["request_encoding"] = "base64"
    pub_data["packet"]["payload"] = btoa("Goodbye, World!")
    resp = requests.post(endpoint, data=json.dumps(pub_data))
    assert resp.status_code == 200
    assert resp.text == "success"
    pub_data["packet"]["payload"] = "Hello, World!"
    pub_data.pop("request_encoding")

    # Missing "path".
    pub_data.pop("path")
    resp = requests.post(endpoint, data=json.dumps(pub_data))
    assert resp.status_code == 400
    assert resp.text == "Request missing required field: path"
    pub_data["path"] = "mypath"

    # Not JSON.
    resp = requests.post(endpoint, data="not json")
    assert resp.status_code == 400
    assert resp.text == "Request must be json."

    # Not JSON object.
    resp = requests.post(endpoint, data=json.dumps(["not object"]))
    assert resp.status_code == 400
    assert resp.text == "Request must be a json object."

    # Standard headers.
    pub_data["standard_headers"] = True
    resp = requests.post(endpoint, data=json.dumps(pub_data))
    assert resp.status_code == 200
    assert resp.text == "success"
    pub_data.pop("standard_headers")

    reader = a0.ReaderSync(a0.File("mypath"), a0.INIT_OLDEST, a0.ITER_NEXT)
    hdrs = []
    msgs = []
    while reader.has_next():
        pkt = reader.next()
        hdrs.append(list(pkt.headers))  # Inspect copies of headers.
        msgs.append(pkt.payload)
    assert len(hdrs) == 3
    assert len(msgs) == 3
    assert msgs == [b"Hello, World!", b"Goodbye, World!", b"Hello, World!"]

    for hdr in hdrs[:-1]:
        assert sorted([k for k, v in hdr]) == ["xyz", "zzz"]

    assert sorted([k for k, v in hdrs[-1]]) == [
        "a0_time_mono",
        "a0_time_wall",
        "a0_transport_seq",
        "a0_writer_id",
        "a0_writer_seq",
        "xyz",
        "zzz",
    ]


def test_rpc(sandbox):
    ns = types.SimpleNamespace()
    ns.collected_requests = []

    def on_request(req):
        ns.collected_requests.append(req.pkt.payload)
        req.reply(f"success_{len(ns.collected_requests) - 1}")

    server = a0.RpcServer("mytopic", on_request, None)

    endpoint = f"http://localhost:{os.environ['PORT_STR']}/api/rpc"
    rpc_data = {
        "topic": "mytopic",
        "packet": {
            "payload": "",
        },
    }

    # Normal request.
    rpc_data["packet"]["payload"] = "request_0"
    resp = requests.post(endpoint, data=json.dumps(rpc_data))
    assert resp.status_code == 200
    assert sorted([k for k, v in resp.json()["headers"]]) == [
        "a0_dep",
        "a0_req_id",
        "a0_rpc_type",
        "a0_time_mono",
        "a0_time_wall",
        "a0_transport_seq",
        "a0_writer_id",
        "a0_writer_seq",
    ]
    assert resp.json()["payload"] == "success_0"

    # Missing "topic".
    rpc_data.pop("topic")
    resp = requests.post(endpoint, data=json.dumps(rpc_data))
    assert resp.status_code == 400
    assert resp.text == "Request missing required field: topic"
    rpc_data["topic"] = "mytopic"

    # Not JSON.
    resp = requests.post(endpoint, data="not json")
    assert resp.status_code == 400
    assert resp.text == "Request must be json."

    # Not JSON object.
    resp = requests.post(endpoint, data=json.dumps("not object"))
    assert resp.status_code == 400
    assert resp.text == "Request must be a json object."

    # Base64 Request Encoding.
    rpc_data["packet"]["payload"] = btoa("request_1")
    rpc_data["request_encoding"] = "base64"
    resp = requests.post(endpoint, data=json.dumps(rpc_data))
    assert resp.status_code == 200
    assert resp.json()["payload"] == "success_1"
    del rpc_data["request_encoding"]

    # Base64 Response Encoding.
    print("Base64 Response Encoding.", flush=True, file=sys.stderr)
    rpc_data["packet"]["payload"] = "request_2"
    rpc_data["response_encoding"] = "base64"
    resp = requests.post(endpoint, data=json.dumps(rpc_data))
    assert resp.status_code == 200
    assert atob(resp.json()["payload"]) == "success_2"

    assert ns.collected_requests == [b"request_0", b"request_1", b"request_2"]


async def test_read(sandbox):
    endpoint = f"ws://localhost:{os.environ['PORT_STR']}/wsapi/read"
    sub_data = {
        "path": "myread",
        "init": "OLDEST",
        "iter": "NEXT",
    }
    w = a0.Writer(a0.File("myread"))

    w.write("payload 0")
    w.write("payload 1")
    async with websockets.connect(endpoint) as ws:
        await ws.send(json.dumps(sub_data))

        try:
            pkt = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert pkt["payload"] == "payload 0"
        except asyncio.TimeoutError:
            assert False

        try:
            pkt = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert pkt["payload"] == "payload 1"
        except asyncio.TimeoutError:
            assert False

        timed_out = False
        try:
            await asyncio.wait_for(ws.recv(), timeout=3.0)
        except asyncio.TimeoutError:
            timed_out = True
        assert timed_out

        w.write("payload 2")
        try:
            pkt = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert pkt["payload"] == "payload 2"
        except asyncio.TimeoutError:
            assert False

    sub_data["response_encoding"] = "base64"
    sub_data["scheduler"] = "ON_ACK"
    async with websockets.connect(endpoint) as ws:
        await ws.send(json.dumps(sub_data))

        try:
            pkt = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert atob(pkt["payload"]) == "payload 0"
        except asyncio.TimeoutError:
            assert False

        timed_out = False
        try:
            await asyncio.wait_for(ws.recv(), timeout=1.0)
        except asyncio.TimeoutError:
            timed_out = True
        assert timed_out

        await ws.send("ACK")
        try:
            pkt = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert atob(pkt["payload"]) == "payload 1"
        except asyncio.TimeoutError:
            assert False

        timed_out = False
        try:
            await asyncio.wait_for(ws.recv(), timeout=1.0)
        except asyncio.TimeoutError:
            timed_out = True
        assert timed_out

        await ws.send("ACK")
        try:
            pkt = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert atob(pkt["payload"]) == "payload 2"
        except asyncio.TimeoutError:
            assert False


async def test_sub(sandbox):
    endpoint = f"ws://localhost:{os.environ['PORT_STR']}/wsapi/sub"
    sub_data = {
        "topic": "mytopic",
        "init": "OLDEST",
        "iter": "NEXT",
    }
    p = a0.Publisher("mytopic")

    p.pub("payload 0")
    p.pub("payload 1")
    async with websockets.connect(endpoint) as ws:
        await ws.send(json.dumps(sub_data))

        try:
            pkt = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert pkt["payload"] == "payload 0"
        except asyncio.TimeoutError:
            assert False

        try:
            pkt = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert pkt["payload"] == "payload 1"
        except asyncio.TimeoutError:
            assert False

        timed_out = False
        try:
            await asyncio.wait_for(ws.recv(), timeout=3.0)
        except asyncio.TimeoutError:
            timed_out = True
        assert timed_out

        p.pub("payload 2")
        try:
            pkt = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert pkt["payload"] == "payload 2"
        except asyncio.TimeoutError:
            assert False

    sub_data["response_encoding"] = "base64"
    sub_data["scheduler"] = "ON_ACK"
    async with websockets.connect(endpoint) as ws:
        await ws.send(json.dumps(sub_data))

        try:
            pkt = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert atob(pkt["payload"]) == "payload 0"
        except asyncio.TimeoutError:
            assert False

        timed_out = False
        try:
            await asyncio.wait_for(ws.recv(), timeout=1.0)
        except asyncio.TimeoutError:
            timed_out = True
        assert timed_out

        await ws.send("ACK")
        try:
            pkt = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert atob(pkt["payload"]) == "payload 1"
        except asyncio.TimeoutError:
            assert False

        timed_out = False
        try:
            await asyncio.wait_for(ws.recv(), timeout=1.0)
        except asyncio.TimeoutError:
            timed_out = True
        assert timed_out

        await ws.send("ACK")
        try:
            pkt = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert atob(pkt["payload"]) == "payload 2"
        except asyncio.TimeoutError:
            assert False


async def test_prpc(sandbox):
    endpoint = f"ws://localhost:{os.environ['PORT_STR']}/wsapi/prpc"
    prpc_data = {
        "topic": "mytopic",
    }

    connect_ids = []

    def onconnect(conn):
        connect_ids.append(conn.pkt.id)
        for i in range(3):
            conn.send(f"payload {i}", False)
        conn.send("server done", True)

    cancel_ids = []

    def oncancel(id_):
        cancel_ids.append(id_)

    server = a0.PrpcServer("mytopic", onconnect, oncancel)  # noqa: F841

    async with websockets.connect(endpoint) as ws:
        await ws.send(json.dumps(prpc_data))

        try:
            for i in range(3):
                pkt = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
                assert pkt["payload"] == f"payload {i}"
                assert not pkt["done"]

            pkt = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert pkt["payload"] == "server done"
            assert pkt["done"]
        except asyncio.TimeoutError:
            assert False
    assert len(cancel_ids) == 1 and connect_ids == cancel_ids

    prpc_data["scheduler"] = "ON_ACK"
    async with websockets.connect(endpoint) as ws:
        await ws.send(json.dumps(prpc_data))

        try:
            pkt = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert pkt["payload"] == "payload 0"
            assert not pkt["done"]
        except asyncio.TimeoutError:
            assert False

        timedout = False
        try:
            pkt = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
        except asyncio.TimeoutError:
            timedout = True
        assert timedout

        for i in range(1, 3):
            try:
                await ws.send("ACK")
                pkt = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
                assert pkt["payload"] == f"payload {i}"
                assert not pkt["done"]
            except asyncio.TimeoutError:
                assert False

        try:
            await ws.send("ACK")
            pkt = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert pkt["payload"] == "server done"
            assert pkt["done"]
        except asyncio.TimeoutError:
            assert False

    assert len(cancel_ids) == 2 and connect_ids == cancel_ids

    async with websockets.connect(endpoint) as ws:
        await ws.send(json.dumps(prpc_data))

        try:
            pkt = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert pkt["payload"] == "payload 0"
            assert not pkt["done"]
        except asyncio.TimeoutError:
            assert False

        timedout = False
        try:
            pkt = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
        except asyncio.TimeoutError:
            timedout = True
        assert timedout

    assert len(cancel_ids) == 3 and connect_ids == cancel_ids
