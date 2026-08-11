"""Shared fixtures: fakes for the three external systems the app talks to.

The app depends on SNS (boto3), the `wg`/`wg-quick` CLIs (subprocess) and
api.ipify.org (requests). Each gets a small hand-written fake rather than a
bare MagicMock, so tests can assert on recorded calls and so the fakes can
model state changes (bringing an interface up really does flip the status).
"""

import subprocess
from dataclasses import dataclass, field
from unittest.mock import MagicMock

import pytest

from vpn_client import app as app_module

VPN_TOPIC_ARN = "arn:aws:sns:eu-west-1:123456789012:wireguard-vpn-topic"
OTHER_TOPIC_ARN = "arn:aws:sns:eu-west-1:123456789012:some-other-topic"
VPN_TAGS = {"application-name": "wireguard-vpn"}
PUBLIC_IP = "203.0.113.42"


class FakeSnsClient:
    """Stand-in for the boto3 SNS client, covering only the three calls used."""

    def __init__(self, topics: dict[str, dict[str, str]]):
        self.topics = topics
        self.published: list[tuple[str, str]] = []

    def list_topics(self):
        return {"Topics": [{"TopicArn": arn} for arn in self.topics]}

    def list_tags_for_resource(self, ResourceArn):  # noqa: N803 - boto3 kwarg name
        return {"Tags": [{"Key": k, "Value": v} for k, v in self.topics[ResourceArn].items()]}

    def publish(self, TopicArn, Message):  # noqa: N803 - boto3 kwarg names
        self.published.append((TopicArn, Message))
        return {"MessageId": "fake-message-id"}


@dataclass
class SnsHarness:
    """Bundles the fake client with the mocks used to reach it."""

    client: FakeSnsClient
    session_factory: MagicMock

    def set_topics(self, topics: dict[str, dict[str, str]]) -> None:
        self.client.topics = topics


@pytest.fixture
def sns(monkeypatch) -> SnsHarness:
    """Patch boto3 so start_vpn() sees a single correctly tagged VPN topic."""
    client = FakeSnsClient({VPN_TOPIC_ARN: dict(VPN_TAGS)})
    session = MagicMock()
    session.client.return_value = client
    session_factory = MagicMock(return_value=session)
    monkeypatch.setattr(app_module.boto3.session, "Session", session_factory)
    return SnsHarness(client=client, session_factory=session_factory)


@dataclass
class FakeWireguard:
    """Records wg/wg-quick invocations and models the interface going up/down."""

    interface_up: bool = False
    calls: list[list[str]] = field(default_factory=list)

    def run(self, cmd, check=False, capture_output=False):
        self.calls.append(list(cmd))
        if cmd[:2] == ["sudo", "wg-quick"]:
            self.interface_up = cmd[2] == "up"
        stdout = b"interface: wg1\n  public key: abc\n" if self.interface_up else b""
        return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr=b"")


@pytest.fixture
def wireguard(monkeypatch) -> FakeWireguard:
    """Patch subprocess.run in the app module; interface starts down."""
    fake = FakeWireguard()
    monkeypatch.setattr(app_module.subprocess, "run", fake.run)
    return fake


@pytest.fixture
def public_ip(monkeypatch) -> MagicMock:
    """Patch the api.ipify.org lookup, returning PUBLIC_IP."""
    response = MagicMock()
    response.text = PUBLIC_IP
    get = MagicMock(return_value=response)
    monkeypatch.setattr(app_module.requests, "get", get)
    return get


@pytest.fixture
def client(sns, wireguard, public_ip):
    """Flask test client with every external dependency faked out."""
    app_module.app.config.update(TESTING=True)
    with app_module.app.test_client() as test_client:
        yield test_client
