from .b64 import atob
import a0
import asyncio
import json
import websockets


async def test_default_scheduler(api_proc):
    p = a0.Publisher("mytopic")
    p.pub("payload 0")
    p.pub("payload 1")

    async with websockets.connect(api_proc.addr("wsapi", "sub")) as ws:
        await ws.send(json.dumps({
            "topic": "mytopic",
            "init": "OLDEST",
        }))

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


async def test_nonutf8_noencoder(api_proc):
    p = a0.Publisher("mytopic")
    p.pub(b"y8\xa1\xb1:\xca,\x11\xe0,\xf8\xd5\xe4\xb9u\x89")

    caught = False
    try:
        async with websockets.connect(api_proc.addr("wsapi", "sub")) as ws:
            await ws.send(json.dumps({
                "topic": "mytopic",
                "init": "OLDEST",
            }))
            await asyncio.wait_for(ws.recv(), timeout=1.0)
    except websockets.ConnectionClosedError as e:
        caught = True
        assert e.code == 1011
        assert e.reason == "[json.exception.type_error.316] invalid UTF-8 byte at index 2: 0xA1"
    assert caught


async def test_onack_scheduler(api_proc):
    p = a0.Publisher("mytopic")
    p.pub("payload 0")
    p.pub("payload 1")

    async with websockets.connect(api_proc.addr("wsapi", "sub")) as ws:
        await ws.send(
            json.dumps({
                "topic": "mytopic",
                "init": "OLDEST",
                "response_encoding": "base64",
                "scheduler": "ON_ACK",
            }))

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


async def test_init_0(api_proc):
    p = a0.Publisher("mytopic")
    p.pub("payload 0")
    p.pub("payload 1")

    async with websockets.connect(api_proc.addr("wsapi", "sub")) as ws:
        await ws.send(json.dumps({
            "topic": "mytopic",
            "init": 0,
        }))

        try:
            pkt = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert pkt["payload"] == "payload 0"
            assert dict(pkt["headers"])["a0_transport_seq"] == "0"
            pkt = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert pkt["payload"] == "payload 1"
            assert dict(pkt["headers"])["a0_transport_seq"] == "1"
        except asyncio.TimeoutError:
            assert False


async def test_init_1(api_proc):
    p = a0.Publisher("mytopic")
    p.pub("payload 0")
    p.pub("payload 1")
    p.pub("payload 2")

    async with websockets.connect(api_proc.addr("wsapi", "sub")) as ws:
        await ws.send(json.dumps({
            "topic": "mytopic",
            "init": 1,
        }))

        try:
            pkt = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert pkt["payload"] == "payload 1"
            assert dict(pkt["headers"])["a0_transport_seq"] == "1"
            pkt = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert pkt["payload"] == "payload 2"
            assert dict(pkt["headers"])["a0_transport_seq"] == "2"
        except asyncio.TimeoutError:
            assert False


async def test_init_1_newest(api_proc):
    p = a0.Publisher("mytopic")
    p.pub("payload 0")
    p.pub("payload 1")
    p.pub("payload 2")

    async with websockets.connect(api_proc.addr("wsapi", "sub")) as ws:
        await ws.send(
            json.dumps({
                "topic": "mytopic",
                "init": 1,
                "iter": "NEWEST",
            }))

        try:
            pkt = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert pkt["payload"] == "payload 2"
            assert dict(pkt["headers"])["a0_transport_seq"] == "2"
        except asyncio.TimeoutError:
            assert False
