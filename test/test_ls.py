import a0
import requests


def test_empty(api_proc):
    resp = requests.get(api_proc.addr("api", "ls"))

    assert resp.status_code == 200
    assert resp.headers["Access-Control-Allow-Origin"] == "*"
    assert resp.json() == []


def test_populated(api_proc):
    a0.File("aaa/bbb.pubsub.a0")
    a0.File("aaa/ccc.pubsub.a0")
    a0.File("bbb/ddd.rpc.a0")

    resp = requests.get(api_proc.addr("api", "ls"))
    assert resp.status_code == 200
    assert resp.json() == [
        "aaa/bbb.pubsub.a0",
        "aaa/ccc.pubsub.a0",
        "bbb/ddd.rpc.a0",
    ]
