#!/usr/bin/env python3

import alephzero as a0
from aiohttp import web, WSMsgType
import aiohttp_cors
import asyncio
import base64
import json
import os

class Namespace:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __repr__(self):
        keys = sorted(self.__dict__)
        items = ("{}={!r}".format(k, self.__dict__[k]) for k in keys)
        return "{}({})".format(type(self).__name__, ", ".join(items))

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __getattr__(self, name):
        return self.__dict__.get(name, None)

# fetch("http://${api_addr}/api/ls")
# .then((r) => { return r.text() })
# .then((msg) => { console.log(msg) })
async def ls_handler(request):
    cmd = None
    if request.body_exists:
        cmd = await request.json()

    def describe(filename):
        protocol, container, topic = filename.split('__')
        if cmd and cmd.get('long', False):
            print('TODO: ls -l')
        if cmd and cmd.get('all', False):
            print('TODO: ls -a')
        return {
            'protocol': protocol,
            'container': container,
            'topic': topic,
        }

    return web.Response(text=json.dumps([
        describe(filename) for filename in os.listdir('/dev/shm')
    ]))

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

    p = a0.Publisher(tm.publisher_topic(cmd['topic']))
    p.pub(a0.Packet(
        cmd['packet']['headers'],
        base64.b64decode(cmd['packet']['payload'])))

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

    ns = Namespace(loop = asyncio.get_event_loop())

    async for msg in ws:
        if msg.type == WSMsgType.TEXT:
            if msg.data == 'close':
                break
            cmd = json.loads(msg.data)
            tm = a0.TopicManager('''{{
                "container": "{container}",
                "subscriber_maps": {{
                    "topic": {{
                        "container": "{container}",
                        "topic": "{topic}"
                    }}
                }}
            }}'''.format(container=cmd['container'], topic=cmd['topic']))
            init_ = {
                'OLDEST': a0.INIT_OLDEST,
                'MOST_RECENT': a0.INIT_MOST_RECENT,
                'AWAIT_NEW': a0.INIT_AWAIT_NEW,
            }[cmd['init']]
            iter_ = {
                'NEXT': a0.ITER_NEXT,
                'NEWEST': a0.ITER_NEWEST,
            }[cmd['iter']]
            def callback(pkt):
                asyncio.ensure_future(ws.send_json({
                    'headers': pkt.headers,
                    'payload': base64.b64encode(pkt.payload.encode('utf-8')).decode('utf-8'),
                }), loop=ns.loop)
            ns.sub = a0.Subscriber(tm.subscriber_topic('topic'), init_, iter_, callback)
        elif msg.type == WSMsgType.ERROR:
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

    ns = Namespace(loop = asyncio.get_event_loop())

    tm = a0.TopicManager('''{{
        "container": "{container}",
        "rpc_client_maps": {{
            "topic": {{
                "container": "{container}",
                "topic": "{topic}"
            }}
        }}
    }}'''.format(container=cmd['container'], topic=cmd['topic']))

    rc = a0.RpcClient(tm.rpc_client_topic('topic'))
    req = a0.Packet(
        cmd['packet']['headers'],
        base64.b64decode(cmd['packet']['payload']))

    fut = asyncio.Future()
    def callback(pkt):
        ns.loop.call_soon_threadsafe(fut.set_result, {
            'headers': pkt.headers,
            'payload': base64.b64encode(pkt.payload.encode('utf-8')).decode('utf-8'),
        })

    rc.send(req, callback)

    return web.Response(text=json.dumps(await fut))


app = web.Application()
app.add_routes([web.get('/api/ls', ls_handler),
                web.post('/api/ls', ls_handler),
                web.post('/api/pub', pub_handler),
                web.get('/api/sub', sub_handler),
                web.post('/api/rpc', rpc_handler)])

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
