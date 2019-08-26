#!/usr/bin/env python3

import alephzero as a0
from aiohttp import web, WSMsgType
import aiohttp_cors
import asyncio
import base64
import json

class Namespace:
    pass

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

    tm = a0.TopicManager('''{{"container": "{}"}}'''.format(cmd['container']))
    topic = tm.open_publisher_topic(cmd['topic'])

    p = a0.Publisher(topic)

    hdrs = list(cmd['packet']['headers'].items())

    p.pub(a0.Packet(hdrs, base64.b64decode(cmd['packet']['payload'])))
    p.close()

    topic.close()
    tm.close()
    return web.Response(text='success')

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

    ns = Namespace()
    ns.tm = None
    ns.topic = None
    ns.sub = None

    async for msg in ws:
        if msg.type == WSMsgType.TEXT:
            if msg.data == 'close':
                break
            cmd = json.loads(msg.data)
            ns.tm = a0.TopicManager('''{{
                "container": "{container}",
                "subscriber_maps": {{
                    "topic": {{
                        "container": "{container}",
                        "topic": "{topic}"
                    }}
                }}
            }}'''.format(container=cmd['container'], topic=cmd['topic']))
            print(cmd)
            ns.topic = ns.tm.open_subscriber_topic('topic')
            init_ = {
                'OLDEST': a0.INIT_OLDEST,
                'MOST_RECENT': a0.INIT_MOST_RECENT,
                'AWAIT_NEW': a0.INIT_AWAIT_NEW,
            }[cmd['init']]
            iter_ = {
                'NEXT': a0.ITER_NEXT,
                'NEWEST': a0.ITER_NEWEST,
            }[cmd['iter']]
            ns.loop = asyncio.get_event_loop()
            def callback(pkt):
                asyncio.ensure_future(ws.send_json({
                    'headers': pkt.headers,
                    'payload': base64.b64encode(pkt.payload.encode('utf-8')).decode('utf-8'),
                }), loop=ns.loop)
            ns.sub = a0.Subscriber(ns.topic, init_, iter_, callback)
        elif msg.type == WSMsgType.ERROR:
            break

    if ns.sub:
        ns.sub.await_close()
    if ns.topic:
        ns.topic.close()
    if ns.tm:
        ns.tm.close()


app = web.Application()
app.add_routes([web.post('/api/pub', pub_handler),
                web.get('/api/sub', sub_handler)])

cors = aiohttp_cors.setup(app, defaults={
    "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
        )
})
for route in list(app.router.routes()):
    cors.add(route)

web.run_app(app, port=24880)
