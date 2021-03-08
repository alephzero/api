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

    def start(self, use_valgrind=True):
        assert not self.api_proc

        cmd = ["/api.bin"]
        if use_valgrind:
            valgrind_args = [
                "--leak-check=full",
                "--error-exitcode=125",
            ]
            cmd = ["valgrind"] + valgrind_args + cmd

        self.api_proc = subprocess.Popen(cmd, env=os.environ.copy())

        ns = types.SimpleNamespace()

        ns.state = RunApi.State.CREATED
        ns.state_cv = threading.Condition()

        def _on_heartbeat_detected():
            with ns.state_cv:
                ns.state = RunApi.State.STARTED
                ns.state_cv.notify_all()

        def _on_heartbeat_missed():
            with ns.state_cv:
                ns.state = RunApi.State.DEAD
                ns.state_cv.notify_all()

        self._heartbeat_listener = a0.HeartbeatListener("api",
                                                        _on_heartbeat_detected,
                                                        _on_heartbeat_missed)

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


@pytest.fixture()
def leaky_sandbox():
    tmp_dir = tempfile.TemporaryDirectory(prefix="/dev/shm/")
    os.environ["A0_ROOT"] = tmp_dir.name
    os.environ["PORT_STR"] = str(random.randint(49152, 65535))
    api = RunApi()
    api.start(use_valgrind=False)
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
    assert resp.json() == [
        {
            "filename": "a0_heartbeat__api",
            "protocol": "heartbeat",
            "container": "api",
        },
    ]

    a0.File("a0_pubsub__aaa__bbb")
    a0.File("a0_pubsub__aaa__ccc")
    a0.File("a0_rpc__bbb__ddd")

    resp = requests.get(f"http://localhost:{os.environ['PORT_STR']}/api/ls")
    assert resp.status_code == 200
    assert resp.json() == [
        {
            "filename": "a0_heartbeat__api",
            "protocol": "heartbeat",
            "container": "api",
        },
        {
            "filename": "a0_pubsub__aaa__bbb",
            "protocol": "pubsub",
            "container": "aaa",
            "topic": "bbb",
        },
        {
            "filename": "a0_pubsub__aaa__ccc",
            "protocol": "pubsub",
            "container": "aaa",
            "topic": "ccc",
        },
        {
            "filename": "a0_rpc__bbb__ddd",
            "protocol": "rpc",
            "container": "bbb",
            "topic": "ddd",
        },
    ]


def test_pub(sandbox):
    endpoint = f"http://localhost:{os.environ['PORT_STR']}/api/pub"
    pub_data = {
        "container": "aaa",
        "topic": "bbb",
        "packet": {
            "payload": btoa("Hello, World!"),
        },
    }

    # Normal publish.
    resp = requests.post(endpoint, data=json.dumps(pub_data))
    assert resp.status_code == 200
    assert resp.text == "success"

    # None request_encoding.
    pub_data["request_encoding"] = "none"
    pub_data["packet"]["payload"] = "Goodbye, World!"
    resp = requests.post(endpoint, data=json.dumps(pub_data))
    assert resp.status_code == 200
    assert resp.text == "success"
    pub_data["packet"]["payload"] = btoa("Hello, World!")
    pub_data.pop("request_encoding")

    # Missing "container".
    pub_data.pop("container")
    resp = requests.post(endpoint, data=json.dumps(pub_data))
    assert resp.status_code == 400
    assert resp.text == "Request missing required field: container"
    pub_data["container"] = "aaa"

    # Missing "topic".
    pub_data.pop("topic")
    resp = requests.post(endpoint, data=json.dumps(pub_data))
    assert resp.status_code == 400
    assert resp.text == "Request missing required field: topic"
    pub_data["topic"] = "bbb"

    # Not JSON.
    resp = requests.post(endpoint, data="not json")
    assert resp.status_code == 400
    assert resp.text == "Request must be json."

    # Not JSON object.
    resp = requests.post(endpoint, data=json.dumps(["not object"]))
    assert resp.status_code == 400
    assert resp.text == "Request must be a json object."

    tm = a0.TopicManager({"container": "aaa"})
    sub = a0.SubscriberSync(tm.publisher_topic("bbb"), a0.INIT_OLDEST,
                            a0.ITER_NEXT)
    msgs = []
    while sub.has_next():
        msgs.append(sub.next().payload)
    assert len(msgs) == 2
    assert msgs == [b"Hello, World!", b"Goodbye, World!"]


def test_rpc(sandbox):
    ns = types.SimpleNamespace()
    ns.collected_requests = []

    def on_request(req):
        ns.collected_requests.append(req.pkt.payload)
        req.reply(f"success_{len(ns.collected_requests) - 1}")

    tm = a0.TopicManager({"container": "aaa"})
    topic = tm.rpc_server_topic("bbb")
    server = a0.RpcServer(topic, on_request, None)

    endpoint = f"http://localhost:{os.environ['PORT_STR']}/api/rpc"
    rpc_data = {
        "container": "aaa",
        "topic": "bbb",
        "packet": {
            "payload": "",
        },
    }

    # Normal request.
    rpc_data["packet"]["payload"] = btoa("request_0")
    resp = requests.post(endpoint, data=json.dumps(rpc_data))
    assert resp.status_code == 200
    assert set([k for k, v in resp.json()["headers"]]) == set([
        "a0_dep",
        "a0_publisher_id",
        "a0_publisher_seq",
        "a0_req_id",
        "a0_rpc_type",
        "a0_time_mono",
        "a0_time_wall",
        "a0_transport_seq",
    ])
    assert atob(resp.json()["payload"]) == "success_0"

    # Missing "container".
    rpc_data.pop("container")
    resp = requests.post(endpoint, data=json.dumps(rpc_data))
    assert resp.status_code == 400
    assert resp.text == "Request missing required field: container"
    rpc_data["container"] = "aaa"

    # Missing "topic".
    rpc_data.pop("topic")
    resp = requests.post(endpoint, data=json.dumps(rpc_data))
    assert resp.status_code == 400
    assert resp.text == "Request missing required field: topic"
    rpc_data["topic"] = "bbb"

    # Not JSON.
    resp = requests.post(endpoint, data="not json")
    assert resp.status_code == 400
    assert resp.text == "Request must be json."

    # Not JSON object.
    resp = requests.post(endpoint, data=json.dumps("not object"))
    assert resp.status_code == 400
    assert resp.text == "Request must be a json object."

    # None Request Encoding.
    rpc_data["packet"]["payload"] = "request_1"
    rpc_data["request_encoding"] = "none"
    resp = requests.post(endpoint, data=json.dumps(rpc_data))
    assert resp.status_code == 200
    assert atob(resp.json()["payload"]) == "success_1"
    del rpc_data["request_encoding"]

    # None Response Encoding.
    print("Base64 Response Encoding.", flush=True, file=sys.stderr)
    rpc_data["packet"]["payload"] = btoa("request_2")
    rpc_data["response_encoding"] = "none"
    resp = requests.post(endpoint, data=json.dumps(rpc_data))
    assert resp.status_code == 200
    assert resp.json()["payload"] == "success_2"

    assert ns.collected_requests == [b"request_0", b"request_1", b"request_2"]


async def test_sub(sandbox):
    endpoint = f"ws://localhost:{os.environ['PORT_STR']}/wsapi/sub"
    sub_data = {
        "container": "aaa",
        "topic": "bbb",
        "init": "OLDEST",
        "iter": "NEXT",
    }
    tm = a0.TopicManager({"container": "aaa"})
    p = a0.Publisher(tm.publisher_topic("bbb"))

    p.pub("payload 0")
    p.pub("payload 1")
    async with websockets.connect(endpoint) as ws:
        await ws.send(json.dumps(sub_data))

        try:
            pkt = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert atob(pkt["payload"]) == "payload 0"
        except asyncio.TimeoutError:
            assert False

        try:
            pkt = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert atob(pkt["payload"]) == "payload 1"
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
            assert atob(pkt["payload"]) == "payload 2"
        except asyncio.TimeoutError:
            assert False

    sub_data["response_encoding"] = "none"
    sub_data["scheduler"] = "ON_ACK"
    async with websockets.connect(endpoint) as ws:
        await ws.send(json.dumps(sub_data))

        try:
            pkt = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert pkt["payload"] == "payload 0"
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
            assert pkt["payload"] == "payload 1"
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
            assert pkt["payload"] == "payload 2"
        except asyncio.TimeoutError:
            assert False


async def test_prpc(sandbox):
    endpoint = f"ws://localhost:{os.environ['PORT_STR']}/wsapi/prpc"
    prpc_data = {
        "container": "aaa",
        "topic": "bbb",
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

    tm = a0.TopicManager({"container": "aaa"})
    server = a0.PrpcServer(tm.prpc_server_topic("bbb"), onconnect,
                           oncancel)  # noqa: F841

    async with websockets.connect(endpoint) as ws:
        await ws.send(json.dumps(prpc_data))

        try:
            for i in range(3):
                pkt = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
                assert atob(pkt["payload"]) == f"payload {i}"
                assert not pkt["done"]

            pkt = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert atob(pkt["payload"]) == "server done"
            assert pkt["done"]
        except asyncio.TimeoutError:
            assert False
    assert len(cancel_ids) == 1 and connect_ids == cancel_ids

    prpc_data["scheduler"] = "ON_ACK"
    async with websockets.connect(endpoint) as ws:
        await ws.send(json.dumps(prpc_data))

        try:
            pkt = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert atob(pkt["payload"]) == "payload 0"
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
                assert atob(pkt["payload"]) == f"payload {i}"
                assert not pkt["done"]
            except asyncio.TimeoutError:
                assert False

        try:
            await ws.send("ACK")
            pkt = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert atob(pkt["payload"]) == "server done"
            assert pkt["done"]
        except asyncio.TimeoutError:
            assert False

    assert len(cancel_ids) == 2 and connect_ids == cancel_ids


# TODO(lshamis): Merge this with the test above once the leak is fixed.
# The C++ wrapper for PrpcClient has a bug where data isn't cleaned up if a message
# with done=True doesn't show up before shutdown.
async def test_prpc_leaky(leaky_sandbox):
    endpoint = f"ws://localhost:{os.environ['PORT_STR']}/wsapi/prpc"
    prpc_data = {
        "container": "aaa",
        "topic": "bbb",
        "scheduler": "ON_ACK",
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

    tm = a0.TopicManager({"container": "aaa"})
    server = a0.PrpcServer(tm.prpc_server_topic("bbb"), onconnect, oncancel)

    async with websockets.connect(endpoint) as ws:
        await ws.send(json.dumps(prpc_data))

        try:
            pkt = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert atob(pkt["payload"]) == "payload 0"
            assert not pkt["done"]
        except asyncio.TimeoutError:
            assert False

        timedout = False
        try:
            pkt = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
        except asyncio.TimeoutError:
            timedout = True
        assert timedout

        assert len(cancel_ids) == 0

    assert len(cancel_ids) == 1 and connect_ids == cancel_ids
