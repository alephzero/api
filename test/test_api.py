import a0
import aiohttp
import asyncio
import base64
import enum
import json
import os
import pytest
import shutil
import subprocess
import threading
import types

try:
    from pytest_cov.embed import cleanup_on_sigterm
except ImportError:
    pass
else:
    cleanup_on_sigterm()

pytestmark = pytest.mark.asyncio


class RunApi:

    class State(enum.Enum):
        DEAD = 0
        CREATED = 1
        STARTED = 2

    def __init__(self):
        self._proc = subprocess.Popen(["./entrypoint.py"],
                                      env=os.environ.copy())

        ns = types.SimpleNamespace()

        ns.state = [RunApi.State.CREATED]
        ns.state_cv = threading.Condition()

        def _on_heartbeat_detected():
            with ns.state_cv:
                ns.state[0] = RunApi.State.STARTED
                ns.state_cv.notify_all()

        def _on_heartbeat_missed():
            with ns.state_cv:
                ns.state[0] = RunApi.State.DEAD
                ns.state_cv.notify_all()

        self._heartbeat_listener = a0.HeartbeatListener("api",
                                                        _on_heartbeat_detected,
                                                        _on_heartbeat_missed)

        self._state = ns.state
        self._state_cv = ns.state_cv

    def __del__(self):
        self._proc.terminate()
        self._proc.wait()
        self._proc = None

    def WaitUntilStarted(self, timeout=None):
        with self._state_cv:
            return self._state_cv.wait_for(
                lambda: self._state[0] == RunApi.State.STARTED, timeout=timeout)

    async def WaitUntilStartedAsync(self, timeout=None):
        loop = asyncio.get_event_loop()
        evt = asyncio.Event()

        def unblock():
            self.WaitUntilStarted(timeout=timeout)
            loop.call_soon_threadsafe(evt.set)

        t = threading.Thread(target=unblock)
        t.start()
        await evt.wait()
        t.join()

        with self._state_cv:
            return self._state[0] == RunApi.State.STARTED

    def is_alive(self):
        return self._proc.poll() is None


@pytest.fixture()
async def sandbox():
    os.environ["A0_ROOT"] = "/dev/shm/test_ls/"
    yield RunApi()
    shutil.rmtree("/dev/shm/test_ls", ignore_errors=True)


async def test_ls(sandbox):
    await sandbox.WaitUntilStartedAsync(timeout=1.0)
    async with aiohttp.ClientSession() as session:
        async with session.get("http://localhost:24880/api/ls") as resp:
            assert resp.status == 200
            assert await resp.json() == [
                {
                    "filename": "a0_heartbeat__api",
                    "protocol": "heartbeat",
                    "container": "api",
                },
            ]

        a0.File("a0_pubsub__aaa__bbb")
        a0.File("a0_pubsub__aaa__ccc")
        a0.File("a0_rpc__bbb__ddd")

        async with session.get("http://localhost:24880/api/ls") as resp:
            assert resp.status == 200
            assert await resp.json() == [
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


async def test_pub(sandbox):
    await sandbox.WaitUntilStartedAsync(timeout=1.0)
    first_msg = "Hello, World!"
    second_msg = "Goodbye, World!"
    async with aiohttp.ClientSession() as session:
        endpoint = "http://localhost:24880/api/pub"
        pub_data = {
            "container": "aaa",
            "topic": "bbb",
            "packet": {
                "payload": first_msg,
            },
        }

        # Normal publish.
        async with session.post(endpoint, data=json.dumps(pub_data)) as resp:
            assert resp.status == 200
            assert await resp.text() == "success"

        # Normal publish.
        pub_data["packet"]["payload"] = second_msg
        async with session.post(endpoint, data=json.dumps(pub_data)) as resp:
            assert resp.status == 200
            assert await resp.text() == "success"

        # Missing "container".
        pub_data.pop("container")
        async with session.post(endpoint, data=json.dumps(pub_data)) as resp:
            assert resp.status == 400
            assert await resp.text() == "Missing required 'container' field."
        pub_data["container"] = "aaa"

        # Missing "topic".
        pub_data.pop("topic")
        async with session.post(endpoint, data=json.dumps(pub_data)) as resp:
            assert resp.status == 400
            assert await resp.text() == "Missing required 'topic' field."
        pub_data["topic"] = "bbb"

        # Not JSON.
        async with session.post(endpoint, data="not json") as resp:
            assert resp.status == 400
            assert await resp.text() == "Body must be json."

        # Not JSON object.
        async with session.post(endpoint,
                                data=json.dumps("not object")) as resp:
            assert resp.status == 400
            assert await resp.text() == "Body must be a json object."

        tm = a0.TopicManager({"container": "aaa"})
        sub = a0.SubscriberSync(tm.publisher_topic("bbb"), a0.INIT_OLDEST,
                                a0.ITER_NEXT)
        msgs = []
        while sub.has_next():
            msgs.append(sub.next().payload)
        assert len(msgs) == 2
        assert msgs == [first_msg, second_msg]


async def test_pub_base64(sandbox):
    await sandbox.WaitUntilStartedAsync(timeout=1.0)
    first_msg = "Hello, World!"
    second_msg = "Goodbye, World!"
    async with aiohttp.ClientSession() as session:
        endpoint = "http://localhost:24880/api/pub"
        pub_data = {
            "container": "aaa",
            "topic": "bbb",
            "packet": {
                "payload": base64.b64encode(str.encode(first_msg)).decode("utf-8"),
            },
            "encoding": "base64",
        }

        # Normal publish.
        async with session.post(endpoint, data=json.dumps(pub_data)) as resp:
            assert resp.status == 200
            assert await resp.text() == "success"

        # Normal publish.
        pub_data["packet"]["payload"] = base64.b64encode(
            str.encode(second_msg)).decode("utf-8")
        async with session.post(endpoint, data=json.dumps(pub_data)) as resp:
            assert resp.status == 200
            assert await resp.text() == "success"

        # Missing "container".
        pub_data.pop("container")
        async with session.post(endpoint, data=json.dumps(pub_data)) as resp:
            assert resp.status == 400
            assert await resp.text() == "Missing required 'container' field."
        pub_data["container"] = "aaa"

        # Missing "topic".
        pub_data.pop("topic")
        async with session.post(endpoint, data=json.dumps(pub_data)) as resp:
            assert resp.status == 400
            assert await resp.text() == "Missing required 'topic' field."
        pub_data["topic"] = "bbb"

        # Not JSON.
        async with session.post(endpoint, data="not json") as resp:
            assert resp.status == 400
            assert await resp.text() == "Body must be json."

        # Not JSON object.
        async with session.post(endpoint,
                                data=json.dumps("not object")) as resp:
            assert resp.status == 400
            assert await resp.text() == "Body must be a json object."

        tm = a0.TopicManager({"container": "aaa"})
        sub = a0.SubscriberSync(tm.publisher_topic("bbb"), a0.INIT_OLDEST,
                                a0.ITER_NEXT)
        msgs = []
        while sub.has_next():
            msgs.append(sub.next().payload)
        assert len(msgs) == 2
        assert msgs == [str.encode(first_msg), str.encode(second_msg)]


async def test_rpc(sandbox):
    await sandbox.WaitUntilStartedAsync(timeout=1.0)

    ns = types.SimpleNamespace()
    ns.collected_requests = []

    def on_request(req):
        ns.collected_requests.append(req.pkt.payload.decode("utf-8"))
        req.reply(f"success_{len(ns.collected_requests)}")

    tm = a0.TopicManager({"container": "aaa"})
    topic = tm.rpc_server_topic("bbb")
    server = a0.RpcServer(topic, on_request, None)  # noqa: F841

    async with aiohttp.ClientSession() as session:
        endpoint = "http://localhost:24880/api/rpc"
        rpc_data = {
            "container": "aaa",
            "topic": "bbb",
            "packet": {
                "payload": "",
            },
        }

        # Normal request.
        rpc_data["packet"]["payload"] = "request_0"
        async with session.post(endpoint, data=json.dumps(rpc_data)) as resp:
            assert resp.status == 200
            resp_pkt = await resp.json()
            assert resp_pkt.get("payload", "") == "success_1"

        # Normal request.
        rpc_data["packet"]["payload"] = "request_1"
        async with session.post(endpoint, data=json.dumps(rpc_data)) as resp:
            assert resp.status == 200
            resp_pkt = await resp.json()
            assert resp_pkt.get("payload", "") == "success_2"

        # Missing "container".
        rpc_data.pop("container")
        async with session.post(endpoint, data=json.dumps(rpc_data)) as resp:
            assert resp.status == 400
            assert await resp.text() == "Missing required 'container' field."
        rpc_data["container"] = "aaa"

        # Missing "topic".
        rpc_data.pop("topic")
        async with session.post(endpoint, data=json.dumps(rpc_data)) as resp:
            assert resp.status == 400
            assert await resp.text() == "Missing required 'topic' field."
        rpc_data["topic"] = "bbb"

        # Not JSON.
        async with session.post(endpoint, data="not json") as resp:
            assert resp.status == 400
            assert await resp.text() == "Body must be json."

        # Not JSON object.
        async with session.post(endpoint,
                                data=json.dumps("not object")) as resp:
            assert resp.status == 400
            assert await resp.text() == "Body must be a json object."

    assert ns.collected_requests == ["request_0", "request_1"]


async def test_rpc_base64(sandbox):
    await sandbox.WaitUntilStartedAsync(timeout=1.0)

    ns = types.SimpleNamespace()
    ns.collected_requests = []

    def on_request(req):
        ns.collected_requests.append(req.pkt.payload.decode("utf-8"))
        req.reply(f"success_{len(ns.collected_requests)}")

    tm = a0.TopicManager({"container": "aaa"})
    topic = tm.rpc_server_topic("bbb")
    server = a0.RpcServer(topic, on_request, None)  # noqa: F841

    async with aiohttp.ClientSession() as session:
        endpoint = "http://localhost:24880/api/rpc"
        rpc_data = {
            "container": "aaa",
            "topic": "bbb",
            "packet": {
                "payload": "",
            },
            "encoding": "base64",
        }

        # Normal request.
        rpc_data["packet"]["payload"] = base64.b64encode(b"request_0").decode(
            "utf-8")
        async with session.post(endpoint, data=json.dumps(rpc_data)) as resp:
            assert resp.status == 200
            resp_pkt = await resp.json()
            assert base64.b64decode(resp_pkt.get("payload", "")) == b"success_1"

        # Normal request.
        rpc_data["packet"]["payload"] = base64.b64encode(b"request_1").decode(
            "utf-8")
        async with session.post(endpoint, data=json.dumps(rpc_data)) as resp:
            assert resp.status == 200
            resp_pkt = await resp.json()
            assert base64.b64decode(resp_pkt.get("payload", "")) == b"success_2"

        # Missing "container".
        rpc_data.pop("container")
        async with session.post(endpoint, data=json.dumps(rpc_data)) as resp:
            assert resp.status == 400
            assert await resp.text() == "Missing required 'container' field."
        rpc_data["container"] = "aaa"

        # Missing "topic".
        rpc_data.pop("topic")
        async with session.post(endpoint, data=json.dumps(rpc_data)) as resp:
            assert resp.status == 400
            assert await resp.text() == "Missing required 'topic' field."
        rpc_data["topic"] = "bbb"

        # Not JSON.
        async with session.post(endpoint, data="not json") as resp:
            assert resp.status == 400
            assert await resp.text() == "Body must be json."

        # Not JSON object.
        async with session.post(endpoint,
                                data=json.dumps("not object")) as resp:
            assert resp.status == 400
            assert await resp.text() == "Body must be a json object."

    assert ns.collected_requests == ["request_0", "request_1"]


async def test_ws_pub(sandbox):
    await sandbox.WaitUntilStartedAsync(timeout=1.0)
    async with aiohttp.ClientSession() as session:
        endpoint = "ws://localhost:24880/wsapi/pub"

        ####################
        # Basic test case. #
        ####################

        handshake_data = {
            "container": "aaa",
            "topic": "bbb",
        }

        ws = await session.ws_connect(endpoint)
        await ws.send_str(json.dumps(handshake_data))

        async def send_payload(payload):
            await ws.send_str(json.dumps({"packet": {"payload": payload}}))

        await asyncio.gather(
            send_payload("message_0"),
            send_payload("message_1"),
            send_payload("message_2"),
        )
        await asyncio.sleep(0.1)

        tm = a0.TopicManager({"container": "aaa"})
        sub = a0.SubscriberSync(tm.publisher_topic("bbb"), a0.INIT_OLDEST,
                                a0.ITER_NEXT)
        msgs = set()
        while sub.has_next():
            msgs.add(sub.next().payload)
        assert len(msgs) == 3
        assert msgs == set(["message_0", "message_1", "message_2"])

        await ws.close()

        ##################
        # Bad handshake. #
        ##################

        # Not JSON.
        ws = await session.ws_connect(endpoint)
        await ws.send_str("not json")

        reply = await ws.receive()
        assert reply.type in [aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED]
        assert reply.extra == "Message must be json."
        assert ws.closed

        # Not JSON object.
        ws = await session.ws_connect(endpoint)
        await ws.send_str(json.dumps("not object"))

        reply = await ws.receive()
        assert reply.type in [aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED]
        assert reply.extra == "Message must be a json object."
        assert ws.closed

        # Missing "container".
        ws = await session.ws_connect(endpoint)
        await ws.send_str(json.dumps({"foo": "bar"}))

        reply = await ws.receive()
        assert reply.type in [aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED]
        assert reply.extra == "Missing required 'container' field."
        assert ws.closed

        # Missing "topic".
        ws = await session.ws_connect(endpoint)
        await ws.send_str(json.dumps({"container": "aaa"}))

        reply = await ws.receive()
        assert reply.type in [aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED]
        assert reply.extra == "Missing required 'topic' field."
        assert ws.closed

        ###############
        # Bad packet. #
        ###############

        # Not JSON.
        ws = await session.ws_connect(endpoint)
        await ws.send_str(json.dumps(handshake_data))

        await ws.send_str("not json")

        reply = await ws.receive()
        assert reply.type in [aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED]
        assert reply.extra == "Message must be json."
        assert ws.closed

        # Not JSON object.
        ws = await session.ws_connect(endpoint)
        await ws.send_str(json.dumps(handshake_data))

        await ws.send_str(json.dumps("not object"))

        reply = await ws.receive()
        assert reply.type in [aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED]
        assert reply.extra == "Message must be a json object."
        assert ws.closed


async def test_ws_pub_base64(sandbox):
    await sandbox.WaitUntilStartedAsync(timeout=1.0)
    async with aiohttp.ClientSession() as session:
        endpoint = "ws://localhost:24880/wsapi/pub"

        ####################
        # Basic test case. #
        ####################

        handshake_data = {
            "container": "aaa",
            "topic": "bbb",
            "encoding": "base64",
        }

        ws = await session.ws_connect(endpoint)
        await ws.send_str(json.dumps(handshake_data))

        async def send_payload(payload):
            payload_utf8 = payload.encode("utf-8")
            payload_b64 = base64.b64encode(payload_utf8).decode("utf-8")
            await ws.send_str(json.dumps({"packet": {"payload": payload_b64}}))

        await asyncio.gather(
            send_payload("message_0"),
            send_payload("message_1"),
            send_payload("message_2"),
        )
        await asyncio.sleep(0.1)

        tm = a0.TopicManager({"container": "aaa"})
        sub = a0.SubscriberSync(tm.publisher_topic("bbb"), a0.INIT_OLDEST,
                                a0.ITER_NEXT)
        msgs = set()
        while sub.has_next():
            msgs.add(sub.next().payload)
        assert len(msgs) == 3
        assert msgs == set([b"message_0", b"message_1", b"message_2"])

        await ws.close()

        ##################
        # Bad handshake. #
        ##################

        # Not JSON.
        ws = await session.ws_connect(endpoint)
        await ws.send_str("not json")

        reply = await ws.receive()
        assert reply.type in [aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED]
        assert reply.extra == "Message must be json."
        assert ws.closed

        # Not JSON object.
        ws = await session.ws_connect(endpoint)
        await ws.send_str(json.dumps("not object"))

        reply = await ws.receive()
        assert reply.type in [aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED]
        assert reply.extra == "Message must be a json object."
        assert ws.closed

        # Missing "container".
        ws = await session.ws_connect(endpoint)
        await ws.send_str(json.dumps({"foo": "bar"}))

        reply = await ws.receive()
        assert reply.type in [aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED]
        assert reply.extra == "Missing required 'container' field."
        assert ws.closed

        # Missing "topic".
        ws = await session.ws_connect(endpoint)
        await ws.send_str(json.dumps({"container": "aaa"}))

        reply = await ws.receive()
        assert reply.type in [aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED]
        assert reply.extra == "Missing required 'topic' field."
        assert ws.closed

        ###############
        # Bad packet. #
        ###############

        # Not JSON.
        ws = await session.ws_connect(endpoint)
        await ws.send_str(json.dumps(handshake_data))

        await ws.send_str("not json")

        reply = await ws.receive()
        assert reply.type in [aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED]
        assert reply.extra == "Message must be json."
        assert ws.closed

        # Not JSON object.
        ws = await session.ws_connect(endpoint)
        await ws.send_str(json.dumps(handshake_data))

        await ws.send_str(json.dumps("not object"))

        reply = await ws.receive()
        assert reply.type in [aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED]
        assert reply.extra == "Message must be a json object."
        assert ws.closed
