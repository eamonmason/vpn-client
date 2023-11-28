# VPN Web Client

The idea is that this is a simple web frontend that allows you to:

- toggle which regions a VPN VM is active in
- adjust the IP address allowed for the client that connects to the VM
- start a wireguard session

Please note that this is a basic implementation and may need to be adjusted to fit your specific needs. For example, you might want to add error handling, logging, user authentication etc.

It depends on the vpn-deploy and vpn-image projects.

## Dependencies

Needs a valid `.aws/credentials` file containing a `vpn` profile.

The credentials must have a policy that contains at least:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "VisualEditor0",
            "Effect": "Allow",
            "Action": "sns:Publish",
            "Resource": "arn:aws:sns:*:*:*",
            "Condition": {
                "StringEquals": {
                    "aws:ResourceTag/application-name": "wireguard-vpn"
                }
            }
        },
        {
            "Sid": "VisualEditor1",
            "Effect": "Allow",
            "Action": [
                "sns:ListTopics",
                "sns:ListTagsForResource"
            ],
            "Resource": "arn:aws:sns:*:*:*"
        }
    ]
}
```

- The wireguard `wg-quick` CLI command must be installed.
- poetry and python3 must be installed, e.g.

  ```sh
  sudo apt-get install pipx
    pipx install poetry
    pipx ensurepath    
  ```

## Run as a Service

You can run the application as a service with systemd if you wish.

1. Copy the file `service/vpn-client.service` to `/etc/systemd/system/vpn-client.service`
2. Start it with `systemctl start vpn-client`
3. Automatically get it to start on boot: `systemctl enable vpn-client`
