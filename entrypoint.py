#!/usr/bin/env python3

import a0
from aiohttp import web, WSMsgType
import aiohttp_cors
import asyncio
import base64
import json
import os
import sys
import threading


# fetch("http://${api_addr}/api/ls")
# .then((r) => { return r.text() })
# .then((msg) => { console.log(msg) })
async def ls_handler(request):
    cmd = None
    if request.can_read_body:
        cmd = await request.json()

    def describe(filename):
        if cmd and cmd.get("long", False):
            print("TODO: ls -l")
        if cmd and cmd.get("all", False):
            print("TODO: ls -a")

        try:
            protocol, container, topic = filename.split("__")
            return {
                "filename": filename,
                "protocol": protocol,
                "container": container,
                "topic": topic,
            }

        except:
            return {
                "filename": filename,
                "protocol": "",
                "container": "",
                "topic": "",
            }

    return web.Response(text=json.dumps([
        describe(filename)
        for filename in os.listdir("/dev/shm")]))


# fetch("http://${api_addr}/api/pub", {
#     method: "POST",
#     body: JSON.stringify({
#         container: "...",
#         topic: "...",
#         packet: {
#             headers: [
#                 ["key", "val"],
#                 ...
#             ],
#             payload: window.btoa("..."),
#         },
#     })
# })
# .then((r) => { return r.text() })
# .then((msg) => { console.assert(msg == "success", msg) })
async def pub_handler(request):
    cmd = await request.json()

    if "packet" not in cmd:
        cmd["packet"] = {}
    if "headers" not in cmd["packet"]:
        cmd["packet"]["headers"] = []
    if "payload" not in cmd["packet"]:
        cmd["packet"]["payload"] = ""

    tm = a0.TopicManager(container = cmd["container"])

    p = a0.Publisher(tm.publisher_topic(cmd["topic"]))
    p.pub(a0.Packet(
        cmd["packet"]["headers"],
        base64.b64decode(cmd["packet"]["payload"])))

    return web.Response(text="success")


# ws = new WebSocket("ws://${api_addr}/api/sub")
# ws.onopen = () => {
#     ws.send(JSON.stringify({
#         container: "...",
#         topic: "...",
#         init: "OLDEST",  // or "MOST_RECENT" or "AWAIT_NEW"
#         iter: "NEXT",  // or "NEWEST"
#     }))
# }
# ws.onmessage = (evt) => {
#     ... evt.data ...
# }
async def sub_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    async for msg in ws:
        if msg.type != WSMsgType.TEXT:
            break

        cmd = json.loads(msg.data)

        tm = a0.TopicManager(
            container = "api",
            subscriber_aliases = {
                "topic": cmd,
            }
        )

        init_ = {
            "OLDEST": a0.INIT_OLDEST,
            "MOST_RECENT": a0.INIT_MOST_RECENT,
            "AWAIT_NEW": a0.INIT_AWAIT_NEW,
        }[cmd["init"]]
        iter_ = {"NEXT": a0.ITER_NEXT, "NEWEST": a0.ITER_NEWEST}[cmd["iter"]]

        async for pkt in a0.aio_sub(tm.subscriber_topic("topic"), init_, iter_):
            await ws.send_json({
                "headers": pkt.headers,
                "payload": base64.b64encode(pkt.payload).decode("utf-8"),
            })

        break


# fetch("http://${api_addr}/api/rpc", {
#     method: "POST",
#     body: JSON.stringify({
#         container: "...",
#         topic: "...",
#         packet: {
#             headers: [
#                 ["key", "val"],
#                 ...
#             ],
#             payload: window.btoa("..."),
#         },
#     })
# })
# .then((r) => { return r.text() })
# .then((msg) => { console.log(msg) })
async def rpc_handler(request):
    cmd = await request.json()

    tm = a0.TopicManager(
        container = "api",
        rpc_client_aliases = {
            "topic": cmd,
        }
    )

    client = a0.AioRpcClient(tm.rpc_client_topic("topic"))
    resp = await client.send(a0.Packet(
        cmd["packet"]["headers"],
        base64.b64decode(cmd["packet"]["payload"])))

    return web.Response(text=json.dumps({
        "headers": pkt.headers,
        "payload": base64.b64encode(pkt.payload).decode("utf-8"),
    }))


app = web.Application()
app.add_routes(
    [
        web.get("/api/ls", ls_handler),
        web.post("/api/ls", ls_handler),
        web.post("/api/pub", pub_handler),
        web.get("/api/sub", sub_handler),
        web.post("/api/rpc", rpc_handler),
    ]
)
cors = aiohttp_cors.setup(
    app,
    defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True, expose_headers="*", allow_headers="*"
        )
    },
)
for route in list(app.router.routes()):
    cors.add(route)

web.run_app(app, port=24880)
