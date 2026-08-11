"""Tests for bin/vpn_client.py.

The script does its work at import time, so it is exercised with runpy under a
patched sys.argv and boto3 rather than by importing a function.
"""

import json
import runpy
import sys
from pathlib import Path
from unittest.mock import MagicMock

import boto3
import pytest

from .conftest import OTHER_TOPIC_ARN, VPN_TAGS, VPN_TOPIC_ARN, FakeSnsClient

SCRIPT = Path(__file__).resolve().parent.parent / "bin" / "vpn_client.py"


def run_script(monkeypatch, argv, topics):
    """Run the script, returning (exit_code, fake_sns_client, boto3_client_mock)."""
    sns = FakeSnsClient(topics)
    client_factory = MagicMock(return_value=sns)
    monkeypatch.setattr(sys, "argv", ["vpn_client.py", *argv])
    monkeypatch.setattr(boto3, "client", client_factory)

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_path(str(SCRIPT), run_name="__main__")

    return exc_info.value.code, sns, client_factory


def test_script_publishes_to_the_tagged_vpn_topic(monkeypatch, capsys):
    code, sns, client_factory = run_script(monkeypatch, ["eu-west-2", "198.51.100.7"], {VPN_TOPIC_ARN: dict(VPN_TAGS)})

    assert code == 0
    client_factory.assert_called_once_with("sns", "eu-west-1")
    topic_arn, message = sns.published[0]
    assert topic_arn == VPN_TOPIC_ARN
    assert json.loads(message) == {"region": "eu-west-2", "whitelist_ip": "198.51.100.7"}
    assert "VPN in eu-west-2 being switched on for 198.51.100.7" in capsys.readouterr().out


def test_script_skips_topics_tagged_for_other_applications(monkeypatch):
    code, sns, _ = run_script(
        monkeypatch,
        ["eu-west-2", "198.51.100.7"],
        {
            OTHER_TOPIC_ARN: {"application-name": "some-other-app"},
            VPN_TOPIC_ARN: dict(VPN_TAGS),
        },
    )

    assert code == 0
    assert [arn for arn, _ in sns.published] == [VPN_TOPIC_ARN]


def test_script_exits_non_zero_when_no_topic_matches(monkeypatch, capsys):
    code, sns, _ = run_script(
        monkeypatch, ["eu-west-2", "198.51.100.7"], {OTHER_TOPIC_ARN: {"application-name": "some-other-app"}}
    )

    assert code == 1
    assert sns.published == []
    assert "Unable to publish message" in capsys.readouterr().out


def test_script_exits_non_zero_when_there_are_no_topics(monkeypatch):
    code, sns, _ = run_script(monkeypatch, ["eu-west-2", "198.51.100.7"], {})

    assert code == 1
    assert sns.published == []


def test_script_requires_region_and_whitelist_ip(monkeypatch, capsys):
    code, sns, _ = run_script(monkeypatch, ["eu-west-2"], {VPN_TOPIC_ARN: dict(VPN_TAGS)})

    assert code == 2  # argparse usage error
    assert sns.published == []
    assert "whitelist_ip" in capsys.readouterr().err
