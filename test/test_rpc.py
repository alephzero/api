from .b64 import atob, btoa
import a0
import json
import pytest
import requests
import types


def SIMPLE_REQUEST_JPKT():
    return {
        "topic": "mytopic",
        "packet": {
            "payload": "request",
        },
    }


@pytest.fixture()
def rpc_server():
    ns = types.SimpleNamespace()
    ns.collected_requests = []

    def on_request(req):
        ns.collected_requests.append(req.pkt.payload)
        req.reply("success")

    ns.server = a0.RpcServer("mytopic", on_request, None)

    yield ns


def test_normal(api_proc, rpc_server):
    jpkt = SIMPLE_REQUEST_JPKT()
    resp = requests.post(api_proc.addr("api", "rpc"), data=json.dumps(jpkt))
    assert resp.status_code == 200
    assert sorted([k for k, v in resp.json()["headers"]]) == [
        "a0_dep",
        "a0_req_id",
        "a0_rpc_type",
        "a0_time_mono",
        "a0_time_wall",
        "a0_transport_seq",
        "a0_writer_id",
        "a0_writer_seq",
    ]
    assert resp.json()["payload"] == "success"
    assert rpc_server.collected_requests == [b"request"]


def test_missing_topic(api_proc, rpc_server):
    jpkt = SIMPLE_REQUEST_JPKT()
    jpkt.pop("topic")
    resp = requests.post(api_proc.addr("api", "rpc"), data=json.dumps(jpkt))
    assert resp.status_code == 400
    assert resp.text == "Request missing required field: topic"


def test_invalid_topic(api_proc, rpc_server):
    jpkt = SIMPLE_REQUEST_JPKT()
    jpkt["topic"] = "/"
    resp = requests.post(api_proc.addr("api", "rpc"), data=json.dumps(jpkt))
    assert resp.status_code == 400
    assert resp.text == "Invalid topic name"


def test_not_json(api_proc, rpc_server):
    resp = requests.post(api_proc.addr("api", "rpc"), data="not json")
    assert resp.status_code == 400
    assert resp.text == "Request must be json."


def test_not_json_object(api_proc, rpc_server):
    resp = requests.post(api_proc.addr("api", "rpc"),
                         data=json.dumps("not object"))
    assert resp.status_code == 400
    assert resp.text == "Request must be a json object."


def test_b64_req_encoding(api_proc, rpc_server):
    jpkt = SIMPLE_REQUEST_JPKT()
    jpkt["packet"]["payload"] = btoa("request")
    jpkt["request_encoding"] = "base64"
    resp = requests.post(api_proc.addr("api", "rpc"), data=json.dumps(jpkt))
    assert resp.status_code == 200
    assert resp.json()["payload"] == "success"
    assert rpc_server.collected_requests == [b"request"]


def test_b64_resp_encoding(api_proc, rpc_server):
    jpkt = SIMPLE_REQUEST_JPKT()
    jpkt["response_encoding"] = "base64"
    resp = requests.post(api_proc.addr("api", "rpc"), data=json.dumps(jpkt))
    assert resp.status_code == 200
    assert atob(resp.json()["payload"]) == "success"
