import a0
import asyncio
import json
import websockets


async def test_normal(api_proc):
    a0.Publisher("aaa").pub("")
    a0.Publisher("bbb").pub("")

    async with websockets.connect(api_proc.addr("wsapi", "discover")) as ws:
        await ws.send(json.dumps({
            "protocol": "pubsub",
            "topic": "*b*",
        }))

        try:
            resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert resp["relpath"] == "bbb.pubsub.a0"
            assert resp["topic"] == "bbb"
        except asyncio.TimeoutError:
            assert False

        timed_out = False
        try:
            await asyncio.wait_for(ws.recv(), timeout=3.0)
        except asyncio.TimeoutError:
            timed_out = True
        assert timed_out

        a0.Publisher("bbbbb").pub("")
        try:
            resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert resp["relpath"] == "bbbbb.pubsub.a0"
            assert resp["topic"] == "bbbbb"
        except asyncio.TimeoutError:
            assert False


async def test_recursive_topic(api_proc):
    a0.Publisher("aaa").pub("")
    a0.Publisher("bbb").pub("")
    a0.Publisher("ddd/ccc").pub("")

    async with websockets.connect(api_proc.addr("wsapi", "discover")) as ws:
        await ws.send(json.dumps({
            "protocol": "pubsub",
            "topic": "**/*c*",
        }))

        try:
            resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert resp["relpath"] == "ddd/ccc.pubsub.a0"
            assert resp["topic"] == "ddd/ccc"
        except asyncio.TimeoutError:
            assert False

        a0.Publisher("ddd/ddd/ccc").pub("")
        try:
            resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert resp["relpath"] == "ddd/ddd/ccc.pubsub.a0"
            assert resp["topic"] == "ddd/ddd/ccc"
        except asyncio.TimeoutError:
            assert False
