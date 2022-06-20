from .b64 import atob, btoa
import a0
import asyncio
import json
import pytest
import types
import websockets


@pytest.fixture()
def prpc_server():
    ns = types.SimpleNamespace()
    ns.connect_payloads = []
    ns.connect_ids = []
    ns.cancel_ids = []

    def onconnect(conn):
        ns.connect_payloads.append(conn.pkt.payload)
        ns.connect_ids.append(conn.pkt.id)
        for i in range(3):
            conn.send(f"payload {i}", False)
        conn.send("server done", True)

    def oncancel(id_):
        ns.cancel_ids.append(id_)

    ns.server = a0.PrpcServer("mytopic", onconnect, oncancel)

    yield ns


async def test_normal(api_proc, prpc_server):
    async with websockets.connect(api_proc.addr("wsapi", "prpc")) as ws:
        await ws.send(
            json.dumps({
                "topic": "mytopic",
                "packet": {
                    "payload": "foo",
                }
            }))

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

    assert prpc_server.connect_payloads == [b"foo"]
    assert len(prpc_server.cancel_ids) == 1
    assert prpc_server.connect_ids == prpc_server.cancel_ids


async def test_ack(api_proc, prpc_server):
    async with websockets.connect(api_proc.addr("wsapi", "prpc")) as ws:
        await ws.send(json.dumps({
            "topic": "mytopic",
            "scheduler": "ON_ACK",
        }))

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

    assert len(prpc_server.cancel_ids) == 1
    assert prpc_server.connect_ids == prpc_server.cancel_ids


async def test_missing_topic(api_proc, prpc_server):
    async with websockets.connect(api_proc.addr("wsapi", "prpc")) as ws:
        await ws.send(json.dumps({}))
        caught = False
        try:
            await asyncio.wait_for(ws.recv(), timeout=1.0)
        except websockets.ConnectionClosedError as e:
            assert e.reason == "Request missing required field: topic"
            caught = True
        assert caught


async def test_invalid_topic(api_proc, prpc_server):
    async with websockets.connect(api_proc.addr("wsapi", "prpc")) as ws:
        await ws.send(json.dumps({
            "topic": "/",
        }))
        caught = False
        try:
            await asyncio.wait_for(ws.recv(), timeout=1.0)
        except websockets.ConnectionClosedError as e:
            assert e.reason == "Invalid topic name"
            caught = True
        assert caught


async def test_not_json(api_proc, prpc_server):
    async with websockets.connect(api_proc.addr("wsapi", "prpc")) as ws:
        await ws.send("not json")
        caught = False
        try:
            await asyncio.wait_for(ws.recv(), timeout=1.0)
        except websockets.ConnectionClosedError as e:
            assert e.reason == "Request must be json."
            caught = True
        assert caught


async def test_not_json_object(api_proc, prpc_server):
    async with websockets.connect(api_proc.addr("wsapi", "prpc")) as ws:
        await ws.send(json.dumps("not object"))
        caught = False
        try:
            await asyncio.wait_for(ws.recv(), timeout=1.0)
        except websockets.ConnectionClosedError as e:
            assert e.reason == "Request must be a json object."
            caught = True
        assert caught


async def test_b64_req_encoding(api_proc, prpc_server):
    async with websockets.connect(api_proc.addr("wsapi", "prpc")) as ws:
        await ws.send(
            json.dumps({
                "topic": "mytopic",
                "request_encoding": "base64",
                "packet": {
                    "payload": btoa("foo"),
                }
            }))

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

    assert prpc_server.connect_payloads == [b"foo"]
    assert len(prpc_server.cancel_ids) == 1
    assert prpc_server.connect_ids == prpc_server.cancel_ids


async def test_b64_resp_encoding(api_proc, prpc_server):
    async with websockets.connect(api_proc.addr("wsapi", "prpc")) as ws:
        await ws.send(
            json.dumps({
                "topic": "mytopic",
                "response_encoding": "base64",
            }))

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

    assert len(prpc_server.cancel_ids) == 1
    assert prpc_server.connect_ids == prpc_server.cancel_ids
