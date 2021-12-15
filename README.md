# api
![CI](https://github.com/alephzero/api/workflows/CI/badge.svg?branch=master)
[![codecov](https://codecov.io/gh/alephzero/api/branch/master/graph/badge.svg)](https://codecov.io/gh/alephzero/api)


REST and Websocket API bridge to AlephZero.

## Examples

The following are javascript examples you can run from a serverless-webpage.

The default port is `24880`.

In all the examples below, we show all the available options.

The value on the right hand side of an option is the default.
If the value is marked as `"..."`, that implies that there is no default and the value is required to be set.

### Publish
```js
fetch(`http://${api_addr}/api/pub`, {
    method: "POST",
    body: JSON.stringify({
        topic: "...",                     // required
        packet: {
            headers: [                    // optional
                ["key", "val"],
                ...
            ],
            payload: "...",               // required
        },
        request_encoding: "none",         // optional, one of "none", "base64"
    })
})
.then((r) => { return r.text() })
.then((msg) => { console.assert(msg == "success", msg) })
```

### Subscribe
```js
ws = new WebSocket(`ws://${api_addr}/wsapi/sub`)
ws.onopen = () => {
    ws.send(JSON.stringify({
        topic: "...",                 // required
        init: "...",                  // required, one of "OLDEST", "MOST_RECENT", "AWAIT_NEW"
        iter: "...",                  // required, one of "NEXT", "NEWEST"
        response_encoding: "none",    // optional, one of "none", "base64"
        scheduler: "IMMEDIATE",       // optional, one of "IMMEDIATE", "ON_ACK", "ON_DRAIN"
    }))
}
ws.onmessage = (evt) => {
    ... evt.data ...
}
```

### Rpc Request
```js
fetch(`http://${api_addr}/api/rpc`, {
    method: "POST",
    body: JSON.stringify({
        topic: "...",                     // required
        packet: {
            headers: [                    // optional
                ["key", "val"],
                ...
            ],
            payload: "...",               // required
        },
        request_encoding: "none",         // optional, one of "none", "base64"
        response_encoding: "none",        // optional, one of "none", "base64"
    })
})
.then((r) => { return r.text() })
.then((msg) => { console.log(msg) })
```

### Prpc Request
```js
ws = new WebSocket(`ws://${api_addr}/wsapi/prpc`)
ws.onopen = () => {
    ws.send(JSON.stringify({
        topic: "...",                 // required
        iter: "NEXT",                 // optional, one of "NEXT", "NEWEST"
        request_encoding: "none",     // optional, one of "none", "base64"
        response_encoding: "none",    // optional, one of "none", "base64"
        scheduler: "IMMEDIATE",       // optional, one of "IMMEDIATE", "ON_ACK", "ON_DRAIN"
    }))
}
ws.onmessage = (evt) => {
    ... evt.data ...
}
```

### Logs
```js
ws = new WebSocket(`ws://${api_addr}/wsapi/log`)
ws.onopen = () => {
    ws.send(JSON.stringify({
        topic: "...",                 // required
        level: "INFO",                // optional, one of "DBG", "INFO", "WARN", "ERR", "CRIT"
        init: "...",                  // required, one of "OLDEST", "MOST_RECENT", "AWAIT_NEW"
        iter: "...",                  // required, one of "NEXT", "NEWEST"
        response_encoding: "none",    // optional, one of "none", "base64"
        scheduler: "IMMEDIATE",       // optional, one of "IMMEDIATE", "ON_ACK", "ON_DRAIN"
    }))
}
ws.onmessage = (evt) => {
    ... evt.data ...
}
```

### Discovery
```js
ws = new WebSocket(`ws://${api_addr}/wsapi/discover`)
ws.onopen = () => {
    ws.send(JSON.stringify({
        protocol: "...",              // required, one of "file", "pubsub", "rpc", "prpc", "log", "cfg"
        topic: "**/*",                // optional
        scheduler: "IMMEDIATE",       // optional, one of "IMMEDIATE", "ON_ACK", "ON_DRAIN"
    }))
}
ws.onmessage = (evt) => {
    ... evt.data ...
}
```

## Development

...

## Running the code

Running a pre-compiled docker image:
```sh
docker run \
    --rm -it \
    --name=a0_api \
    --ipc=host \
    --pid=host \
    -p 24880:24880 \
    ghcr.io/alephzero/api:latest
```

or git clone this repo and `./run.sh`
