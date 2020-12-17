#!/usr/bin/env python3

import base64
import json
import os

import a0
import aiohttp
import aiohttp_cors


# fetch(`http://${api_addr}/api/ls`)
# .then((r) => { return r.text() })
# .then((msg) => { console.log(msg) })
async def ls_handler(request):

    def describe(filename):
        description = {"filename": filename}

        if not filename.startswith("a0_"):
            return

        parts = filename.split("__")
        description["protocol"] = parts[0][3:]
        if len(parts) >= 2:
            description["container"] = parts[1]
        if len(parts) >= 3:
            description["topic"] = parts[2]

        return description

    filenames = os.listdir(os.environ.get("A0_ROOT", "/dev/shm"))
    return aiohttp.web.json_response(
        [describe(filename) for filename in sorted(filenames)])


# fetch(`http://${api_addr}/api/pub`, {
#     method: "POST",
#     body: JSON.stringify({
#         container: "...",
#         topic: "...",
#         encoding: "...",
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
    try:
        cmd = await request.json()
    except json.decoder.JSONDecodeError:
        raise aiohttp.web.HTTPBadRequest(body=b"Body must be json.")

    # Check cmd is a dict.
    if type(cmd) != dict:
        raise aiohttp.web.HTTPBadRequest(body=b"Body must be a json object.")

    # Check for required fields.
    if "container" not in cmd:
        raise aiohttp.web.HTTPBadRequest(
            body=b"Missing required 'container' field.")
    if "topic" not in cmd:
        raise aiohttp.web.HTTPBadRequest(
            body=b"Missing required 'topic' field.")

    # Fill optional fields.
    cmd["packet"] = cmd.get("packet", {})
    headers = cmd["packet"].get("headers", [])
    payload = cmd["packet"].get("payload", "")
    encoding = cmd["packet"].get("encoding", "")

    if encoding is "base64":
        payload = base64.b64decode(payload)

    # Find the absolute topic.
    tm = a0.TopicManager(container=cmd["container"])
    topic = tm.publisher_topic(cmd["topic"])

    # Perform requested action.
    p = a0.Publisher(topic)
    p.pub(headers, payload)

    return aiohttp.web.Response(text="success")


# fetch(`http://${api_addr}/api/rpc`, {
#     method: "POST",
#     body: JSON.stringify({
#         container: "...",
#         topic: "...",
#         encoding: "...",
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
    try:
        cmd = await request.json()
    except json.decoder.JSONDecodeError:
        raise aiohttp.web.HTTPBadRequest(body=b"Body must be json.")

    # Check cmd is a dict.
    if type(cmd) != dict:
        raise aiohttp.web.HTTPBadRequest(body=b"Body must be a json object.")

    # Check for required fields.
    if "container" not in cmd:
        raise aiohttp.web.HTTPBadRequest(
            body=b"Missing required 'container' field.")
    if "topic" not in cmd:
        raise aiohttp.web.HTTPBadRequest(
            body=b"Missing required 'topic' field.")

    # Fill optional fields.
    cmd["packet"] = cmd.get("packet", {})
    headers = cmd["packet"].get("headers", [])
    payload = cmd["packet"].get("payload", "")
    encoding = cmd["packet"].get("encoding", "")

    if encoding is "base64":
        payload = base64.b64decode(payload)

    # Find the absolute topic.
    tm = a0.TopicManager(container="api", rpc_client_aliases={
        "topic": cmd,
    })
    topic = tm.rpc_client_topic("topic")

    # Perform requested action.
    client = a0.AioRpcClient(topic)
    resp = await client.send(a0.Packet(headers, payload))

    if encoding is "base64":
        resp_payload = base64.b64encode(resp.payload).decode("utf-8")

    return aiohttp.web.json_response({
        "headers": resp.headers,
        "payload": resp_payload,
    })


# ws = new WebSocket(`ws://${api_addr}/wsapi/pub`)
# ws.onopen = () => {
#     ws.send(JSON.stringify({
#         container: "...",
#         topic: "...",
#         encoding: "...",
#     }))
# }
# // later, after onopen completes:
# ws.send(JSON.stringify({
#         packet: {
#             headers: [
#                 ["key", "val"],
#                 ...
#             ],
#             payload: window.btoa("..."),
#         },
# }))
async def pub_wshandler(request):
    ws = aiohttp.web.WebSocketResponse()
    await ws.prepare(request)

    handshake_completed = False

    async for msg in ws:
        if msg.type != aiohttp.WSMsgType.TEXT:
            break

        try:
            cmd = json.loads(msg.data)
        except json.JSONDecodeError:
            await ws.close(message=b"Message must be json.")
            return

        # Check cmd is a dict.
        if type(cmd) != dict:
            await ws.close(message=b"Message must be a json object.")
            return

        if not handshake_completed:
            # Check for required fields.
            if "container" not in cmd:
                await ws.close(message=b"Missing required 'container' field.")
                return
            if "topic" not in cmd:
                await ws.close(message=b"Missing required 'topic' field.")
                return

            # Create a publisher on the absolute topic.
            tm = a0.TopicManager(container=cmd["container"])
            publisher = a0.Publisher(tm.publisher_topic(cmd["topic"]))

            handshake_completed = True
            continue

        # Fill optional fields.
        cmd["packet"] = cmd.get("packet", {})
        headers = cmd["packet"].get("headers", [])
        payload = cmd["packet"].get("payload", "")
        encoding = cmd["packet"].get("encoding", "")

        if encoding is "base64":
            payload = base64.b64decode(payload)

        publisher.pub(headers, payload)


# ws = new WebSocket(`ws://${api_addr}/wsapi/sub`)
# ws.onopen = () => {
#     ws.send(JSON.stringify({
#         container: "...",
#         topic: "...",
#         init: "OLDEST",  // or "MOST_RECENT" or "AWAIT_NEW"
#         iter: "NEXT",  // or "NEWEST"
#         encoding: "...",
#     }))
# }
# ws.onmessage = (evt) => {
#     ... evt.data ...
# }
async def sub_wshandler(request):
    ws = aiohttp.web.WebSocketResponse()
    await ws.prepare(request)

    msg = await ws.receive()
    cmd = json.loads(msg.data)

    tm = a0.TopicManager(container="api", subscriber_aliases={"topic": cmd})

    init_ = {
        "OLDEST": a0.INIT_OLDEST,
        "MOST_RECENT": a0.INIT_MOST_RECENT,
        "AWAIT_NEW": a0.INIT_AWAIT_NEW,
    }[cmd["init"]]
    iter_ = {"NEXT": a0.ITER_NEXT, "NEWEST": a0.ITER_NEWEST}[cmd["iter"]]

    scheduler = cmd.get("scheduler", "IMMEDIATE")
    encoding = cmd.get("encoding", "")


    async for pkt in a0.aio_sub(tm.subscriber_topic("topic"), init_, iter_):
        payload = pkt.payload
        if encoding is "base64":
            payload = base64.b64encode(pkt.payload).decode("utf-8"),
        await ws.send_json({
            "headers": pkt.headers,
            "payload": payload,
        })
        if scheduler == "IMMEDIATE":
            pass
        elif scheduler == "ON_ACK":
            await ws.receive()


a0.InitGlobalTopicManager({"container": "api"})
heartbeat = a0.Heartbeat()

app = aiohttp.web.Application()
app.add_routes([
    aiohttp.web.get("/api/ls", ls_handler),
    aiohttp.web.post("/api/pub", pub_handler),
    aiohttp.web.post("/api/rpc", rpc_handler),
    aiohttp.web.get("/wsapi/pub", pub_wshandler),
    aiohttp.web.get("/wsapi/sub", sub_wshandler),
])
cors = aiohttp_cors.setup(
    app,
    defaults={
        "*":
            aiohttp_cors.ResourceOptions(allow_credentials=True,
                                         expose_headers="*",
                                         allow_headers="*")
    },
)
for route in list(app.router.routes()):
    cors.add(route)

aiohttp.web.run_app(app, port=24880)
