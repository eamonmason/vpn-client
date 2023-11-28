"""
Web application to start VPN connection
"""
import json
import requests
import subprocess

import boto3
from flask import Flask, render_template, request

app = Flask(__name__)


def _get_local_ip():
    response = requests.get('https://api.ipify.org', timeout=20)
    return response.text


@app.route('/', methods=['GET', 'POST'])
def home():
    """
    Home page
    """
    if request.method == 'POST':
        region = request.form.get('region')
        ip_address = request.form.get('ip_address')
        if start_vpn(region, ip_address):
            return 'VPN started'
        else:
            return 'VPN not started'

    return render_template('index.html', ip_address=_get_local_ip(), vpn_status=_get_wg_status())


def start_vpn(region, ip_address) -> bool:
    """
    Start VPN connection
    """
    sess = boto3.session.Session(profile_name='vpn', region_name='eu-west-1')
    sns = sess.client('sns')
    topics = sns.list_topics()['Topics']
    for topic in topics:
        topic_arn = topic['TopicArn']
        tags = sns.list_tags_for_resource(ResourceArn=topic_arn)['Tags']
        for tag in tags:
            if tag['Key'] == 'application-name' and tag['Value'] == 'wireguard-vpn':
                message = json.dumps({"region": region, "whitelist_ip": ip_address})

                sns.publish(TopicArn=topic_arn, Message=message)
                return True
    return False


def _get_wg_status() -> bool:
    """
    Get VPN status: true = enabled; false = disabled
    """
    wg_show_all = subprocess.run(
        ['sudo', 'wg', 'show', 'all'],
        check=True,
        capture_output=True).stdout.decode('utf-8')
    return 'interface: wg1' in wg_show_all


@app.route('/wg', methods=['GET', 'POST'])
def toggle_wg_quick():
    """
    Toggle VPN connection
    """
    if request.method == 'POST':
        if _get_wg_status():
            subprocess.run(['sudo', 'wg-quick', 'down', 'wg1'], check=True)
        else:
            subprocess.run(['sudo', 'wg-quick', 'up', 'wg1'], check=True)
    return f"VPN client enabled: {_get_wg_status()}"


if __name__ == '__main__':
    app.run(debug=True)
    # app.run()
