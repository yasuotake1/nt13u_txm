# tests/test_remoteex.py
import pytest

from meas.remoteexclient import RemoteExClient


HOST = "127.0.0.1"
PORT_CMD = 1001
PORT_DATA = 1002


@pytest.fixture(scope="module")
def re():
    client = RemoteExClient(
        host_cmd=HOST,
        port_cmd=PORT_CMD,
        host_data=HOST,
        port_data=PORT_DATA,
        encoding="ascii",  # 装置がASCII想定。ダメなら外す/変更
    )
    yield client
    client.disconnect()


def test_cameraname(re):
    print(re.camera_name)

