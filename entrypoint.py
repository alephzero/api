#!/usr/bin/env python3

import sys

print('importing a0...', file=sys.stderr)
import a0
print('importing aiohttp...', file=sys.stderr)
from aiohttp import web, WSMsgType
print('importing aiohttp_cors...', file=sys.stderr)
import aiohttp_cors
print('importing others...', file=sys.stderr)
import asyncio
import base64
import json
import os
import sys

print('starting...', file=sys.stderr)

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
    print('sub_handler', request, file=sys.stderr)
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    print('sub_handler prep', file=sys.stderr)

    ns = Namespace(loop = asyncio.get_event_loop())
    ns.loop.set_debug(True)
    ns.close = False

    def handle_exceptions(fut):
        ex = fut.exception()
        if ex is not None:
            print('exception:', ex, file=sys.stderr)
            ns.close = True

    async for msg in ws:
        if ns.close:
            break
        print('sub msg', msg, file=sys.stderr)
        if msg.type == WSMsgType.TEXT:
            print('sub msg txt', file=sys.stderr)
            if msg.data == 'close':
                break
            print('parsing json', file=sys.stderr)
            cmd = json.loads(msg.data)
            print('cmd', cmd, file=sys.stderr)
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
            print('init', init_, file=sys.stderr)
            print('iter', iter_, file=sys.stderr)
            def callback(pkt_view):
                print('off thread callback', file=sys.stderr)
                def cb_helper(pkt):
                    print('on thread callback', file=sys.stderr)
                    fut = asyncio.ensure_future(ws.send_json({
                        'headers': pkt.headers,
                        'payload': base64.b64encode(pkt.payload).decode('utf-8'),
                    }), loop=ns.loop)
                    fut.add_done_callback(handle_exceptions)
                    print('ensured', file=sys.stderr)
                ns.loop.call_soon_threadsafe(cb_helper, a0.Packet(pkt_view))
            print('making sub', file=sys.stderr)
            ns.sub = a0.Subscriber(tm.subscriber_topic('topic'), init_, iter_, callback)
            print('made sub', file=sys.stderr)
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
            'payload': base64.b64encode(pkt.payload).decode('utf-8'),
        })

    rc.send(req, callback)

    return web.Response(text=json.dumps(await fut))


print('creating app', file=sys.stderr)
app = web.Application()
print('adding routes', file=sys.stderr)
app.add_routes([web.get('/api/ls', ls_handler),
                web.post('/api/ls', ls_handler),
                web.post('/api/pub', pub_handler),
                web.get('/api/sub', sub_handler),
                web.post('/api/rpc', rpc_handler)])

print('adding cors', file=sys.stderr)
cors = aiohttp_cors.setup(app, defaults={
    "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
        )
})
for route in list(app.router.routes()):
    cors.add(route)

print('running app', file=sys.stderr)
web.run_app(app, port=24880)
print('app completed', file=sys.stderr)

