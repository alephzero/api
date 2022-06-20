from .b64 import atob
import a0
import asyncio
import json
import websockets


async def test_default_scheduler(api_proc):
    w = a0.Writer(a0.File("myread"))
    w.write("payload 0")
    w.write("payload 1")

    async with websockets.connect(api_proc.addr("wsapi", "read")) as ws:
        await ws.send(json.dumps({
            "path": "myread",
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

        w.write("payload 2")
        try:
            pkt = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert pkt["payload"] == "payload 2"
        except asyncio.TimeoutError:
            assert False


async def test_onack_scheduler(api_proc):
    w = a0.Writer(a0.File("myread"))
    w.write("payload 0")
    w.write("payload 1")

    async with websockets.connect(api_proc.addr("wsapi", "read")) as ws:
        await ws.send(
            json.dumps({
                "path": "myread",
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

        timed_out = False
        try:
            await asyncio.wait_for(ws.recv(), timeout=1.0)
        except asyncio.TimeoutError:
            timed_out = True
        assert timed_out
