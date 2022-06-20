import a0
import enum
import os
import pytest
import random
import subprocess
import tempfile

# TODO(lshamis): Things to test:
# * unclean shutdown.


class RunApi:

    class State(enum.Enum):
        DEAD = 0
        CREATED = 1
        STARTED = 2

    def __init__(self):
        self.api_proc = None

    def start(self):
        assert not self.api_proc

        api_ready = a0.SubscriberSync("api_ready")

        self.api_proc = subprocess.Popen(
            [
                "valgrind", "--leak-check=full", "--error-exitcode=125",
                "bin/api"
            ],
            env=os.environ.copy(),
        )

        api_ready.read_blocking(timeout=3)

    def shutdown(self):
        assert self.api_proc
        self.api_proc.terminate()
        assert self.api_proc.wait() == 0
        self.api_proc = None

    def addr(self, mode, target):
        prefix = {
            "api": "http",
            "wsapi": "ws",
        }[mode]
        return f"{prefix}://localhost:{os.environ['PORT_STR']}/{mode}/{target}"


@pytest.fixture()
def api_proc():
    tmp_dir = tempfile.TemporaryDirectory(prefix="/dev/shm/")
    os.environ["A0_ROOT"] = tmp_dir.name
    os.environ["PORT_STR"] = str(random.randint(49152, 65535))
    api = RunApi()
    api.start()
    yield api
    api.shutdown()
