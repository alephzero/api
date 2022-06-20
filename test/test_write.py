from .b64 import btoa
import a0
import json
import requests


def SIMPLE_JPKT():
    return {
        "path": "mytopic.a0",
        "packet": {
            "headers": [
                ["xyz", "123"],
                ["zzz", "www"],
            ],
            "payload": "Hello, World!",
        },
    }


def verify(want, want_hdrs=[], want_all_hdr_keys=None):
    reader = a0.ReaderSync(a0.File("mytopic.a0"), a0.INIT_OLDEST)
    hdrs = {}
    msgs = []
    while reader.can_read():
        pkt = reader.read()
        for k, v in pkt.headers:
            hdrs.setdefault(k, []).append(v)
        msgs.append(pkt.payload)

    assert msgs == want
    for k, v in want_hdrs:
        assert v in hdrs[k]
    if want_all_hdr_keys is not None:
        assert set(want_all_hdr_keys) == set(hdrs.keys())


def test_normal(api_proc):
    resp = requests.post(api_proc.addr("api", "write"),
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
            "xyz",
            "zzz",
        ],
    )


def test_b64_encode(api_proc):
    jpkt = SIMPLE_JPKT()
    jpkt["request_encoding"] = "base64"
    jpkt["packet"]["payload"] = btoa("Goodbye, World!")
    resp = requests.post(api_proc.addr("api", "write"), data=json.dumps(jpkt))
    assert resp.status_code == 200
    assert resp.text == "success"

    verify([b"Goodbye, World!"])


def test_missing_path(api_proc):
    jpkt = SIMPLE_JPKT()
    jpkt.pop("path")
    resp = requests.post(api_proc.addr("api", "write"), data=json.dumps(jpkt))
    assert resp.status_code == 400
    assert resp.text == "Request missing required field: path"


def test_invalid_path(api_proc):
    jpkt = SIMPLE_JPKT()
    jpkt["path"] = "/"
    resp = requests.post(api_proc.addr("api", "write"), data=json.dumps(jpkt))
    assert resp.status_code == 400
    assert resp.text == "Is a directory"


def test_not_json(api_proc):
    resp = requests.post(api_proc.addr("api", "write"), data="not json")
    assert resp.status_code == 400
    assert resp.text == "Request must be json."


def test_not_json_object(api_proc):
    resp = requests.post(api_proc.addr("api", "write"),
                         data=json.dumps(["not object"]))
    assert resp.status_code == 400
    assert resp.text == "Request must be a json object."


def test_standard_headers(api_proc):
    jpkt = SIMPLE_JPKT()
    jpkt["standard_headers"] = True
    resp = requests.post(api_proc.addr("api", "write"), data=json.dumps(jpkt))
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
