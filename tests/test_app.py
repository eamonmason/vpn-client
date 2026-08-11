"""Tests for the Flask app: routes, SNS publishing and wireguard control."""

import json

import pytest

from vpn_client.app import _get_local_ip, _get_wg_status, start_vpn

from .conftest import OTHER_TOPIC_ARN, PUBLIC_IP, VPN_TAGS, VPN_TOPIC_ARN


def test_get_local_ip_returns_response_body(public_ip):
    assert _get_local_ip() == PUBLIC_IP
    public_ip.assert_called_once_with("https://api.ipify.org", timeout=20)


def test_home_renders_public_ip_into_form(client):
    response = client.get("/")
    assert response.status_code == 200
    assert PUBLIC_IP in response.get_data(as_text=True)


@pytest.mark.parametrize(
    ("interface_up", "expected"),
    [(True, "Enabled"), (False, "Disabled")],
)
def test_home_reports_vpn_status(client, wireguard, interface_up, expected):
    wireguard.interface_up = interface_up

    body = client.get("/").get_data(as_text=True)

    assert f"VPN connection status: {expected}" in body


def test_home_post_starts_vpn(client, sns):
    response = client.post("/", data={"region": "eu-west-2", "ip_address": "198.51.100.7"})

    assert response.get_data(as_text=True) == "VPN started"
    assert sns.client.published == [
        (VPN_TOPIC_ARN, json.dumps({"region": "eu-west-2", "whitelist_ip": "198.51.100.7"}))
    ]


def test_home_post_reports_failure_when_no_vpn_topic(client, sns):
    sns.set_topics({OTHER_TOPIC_ARN: {"application-name": "something-else"}})

    response = client.post("/", data={"region": "eu-west-2", "ip_address": "198.51.100.7"})

    assert response.get_data(as_text=True) == "VPN not started"
    assert sns.client.published == []


def test_start_vpn_uses_the_vpn_profile_and_home_region(sns):
    start_vpn("us-east-1", "198.51.100.7")

    sns.session_factory.assert_called_once_with(profile_name="vpn", region_name="eu-west-1")


def test_start_vpn_publishes_region_and_whitelist_ip(sns):
    assert start_vpn("us-east-1", "198.51.100.7") is True

    topic_arn, message = sns.client.published[0]
    assert topic_arn == VPN_TOPIC_ARN
    assert json.loads(message) == {"region": "us-east-1", "whitelist_ip": "198.51.100.7"}


def test_start_vpn_skips_topics_tagged_for_other_applications(sns):
    sns.set_topics(
        {
            OTHER_TOPIC_ARN: {"application-name": "some-other-app", "env": "prod"},
            VPN_TOPIC_ARN: dict(VPN_TAGS),
        }
    )

    assert start_vpn("eu-north-1", "198.51.100.7") is True
    assert [arn for arn, _ in sns.client.published] == [VPN_TOPIC_ARN]


def test_start_vpn_ignores_topics_with_the_right_tag_key_but_wrong_value(sns):
    sns.set_topics({OTHER_TOPIC_ARN: {"application-name": "wireguard-vpn-staging"}})

    assert start_vpn("eu-north-1", "198.51.100.7") is False
    assert sns.client.published == []


def test_start_vpn_returns_false_when_no_topics_exist(sns):
    sns.set_topics({})

    assert start_vpn("eu-north-1", "198.51.100.7") is False


def test_start_vpn_returns_false_for_untagged_topic(sns):
    sns.set_topics({OTHER_TOPIC_ARN: {}})

    assert start_vpn("eu-north-1", "198.51.100.7") is False


@pytest.mark.parametrize("interface_up", [True, False])
def test_get_wg_status_reflects_the_wg1_interface(wireguard, interface_up):
    wireguard.interface_up = interface_up

    assert _get_wg_status() is interface_up


def test_get_wg_status_shells_out_to_wg_show_all(wireguard):
    _get_wg_status()

    assert wireguard.calls == [["sudo", "wg", "show", "all"]]


def test_toggle_wg_get_does_not_change_the_interface(client, wireguard):
    response = client.get("/wg")

    assert response.get_data(as_text=True) == "VPN client enabled: False"
    assert ["sudo", "wg-quick", "down", "wg1"] not in wireguard.calls
    assert ["sudo", "wg-quick", "up", "wg1"] not in wireguard.calls


def test_toggle_wg_post_brings_the_interface_up_when_down(client, wireguard):
    wireguard.interface_up = False

    response = client.post("/wg")

    assert ["sudo", "wg-quick", "up", "wg1"] in wireguard.calls
    assert wireguard.interface_up is True
    assert response.get_data(as_text=True) == "VPN client enabled: True"


def test_toggle_wg_post_brings_the_interface_down_when_up(client, wireguard):
    wireguard.interface_up = True

    response = client.post("/wg")

    assert ["sudo", "wg-quick", "down", "wg1"] in wireguard.calls
    assert wireguard.interface_up is False
    assert response.get_data(as_text=True) == "VPN client enabled: False"
