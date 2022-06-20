import base64


def btoa(s):
    return base64.b64encode(s.encode("utf-8")).decode("utf-8")


def atob(b):
    return base64.b64decode(b.encode("utf-8")).decode("utf-8")
