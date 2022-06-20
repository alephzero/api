from .b64 import btoa
import a0
import json
import requests


def SIMPLE_JPKT():
    return {
        "topic": "mytopic",
        "packet": {
            "headers": [
                ["xyz", "123"],
                ["zzz", "www"],
            ],
            "payload": "Hello, World!",
        },
    }


def verify(want, want_hdrs=[], want_all_hdr_keys=None):
    sub = a0.SubscriberSync("mytopic", a0.INIT_OLDEST)
    hdrs = {}
    msgs = []
    while sub.can_read():
        pkt = sub.read()
        for k, v in pkt.headers:
            hdrs.setdefault(k, []).append(v)
        msgs.append(pkt.payload)

    assert msgs == want
    for k, v in want_hdrs:
        assert v in hdrs[k]
    if want_all_hdr_keys is not None:
        assert set(want_all_hdr_keys) == set(hdrs.keys())


def test_normal(api_proc):
    resp = requests.post(api_proc.addr("api", "pub"),
                         data=json.dumps(SIMPLE_JPKT()))
    assert resp.status_code == 200
    assert resp.text == "success"

    verify(
        [b"Hello, World!"],
        want_hdrs=[
            ["xyz", "123"],
            ["zzz", "www"],
        ],
        want_all_hdr_keys=[
            "a0_time_mono",
            "a0_time_wall",
            "a0_transport_seq",
            "a0_writer_id",
            "a0_writer_seq",
            "xyz",
            "zzz",
        ],
    )


def test_b64_encode(api_proc):
    jpkt = SIMPLE_JPKT()
    jpkt["request_encoding"] = "base64"
    jpkt["packet"]["payload"] = btoa("Goodbye, World!")
    resp = requests.post(api_proc.addr("api", "pub"), data=json.dumps(jpkt))
    assert resp.status_code == 200
    assert resp.text == "success"

    verify([b"Goodbye, World!"])


def test_missing_topic(api_proc):
    jpkt = SIMPLE_JPKT()
    jpkt.pop("topic")
    resp = requests.post(api_proc.addr("api", "pub"), data=json.dumps(jpkt))
    assert resp.status_code == 400
    assert resp.text == "Request missing required field: topic"


def test_invalid_topic(api_proc):
    jpkt = SIMPLE_JPKT()
    jpkt["topic"] = "/"
    resp = requests.post(api_proc.addr("api", "pub"), data=json.dumps(jpkt))
    assert resp.status_code == 400
    assert resp.text == "Invalid topic name"


def test_not_json(api_proc):
    resp = requests.post(api_proc.addr("api", "pub"), data="not json")
    assert resp.status_code == 400
    assert resp.text == "Request must be json."


def test_not_json_object(api_proc):
    resp = requests.post(api_proc.addr("api", "pub"),
                         data=json.dumps(["not object"]))
    assert resp.status_code == 400
    assert resp.text == "Request must be a json object."
