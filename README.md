# VPN Web Client

The idea is that this is a simple web frontend that allows you to:

- toggle which regions a VPN VM is active in
- adjust the IP address allowed for the client that connects to the VM
- start a wireguard session

Please note that this is a basic implementation and may need to be adjusted to fit your specific needs. For example, you might want to add error handling, logging, user authentication etc.

It depends on the vpn-deploy and vpn-image projects.

## Configuring a device's WireGuard client

Use [`config/wg-client.conf.template`](config/wg-client.conf.template) as the
starting point for each device's WireGuard app (or for the `wg1` interface on
this box).

1. **Generate a key pair on (or for) the device** — every device gets its own
   pair; sharing one key between two devices makes the server flap between
   their endpoints and drops both connections:

   ```sh
   wg genkey | tee device.key | wg pubkey > device.pub
   ```

2. **Register the device with the server** by adding a line
   `<contents-of-device.pub>,10.0.0.X/32` (unique X per device) to the
   `/vpn-wireguard/CLIENT_PEERS` SSM parameter in `eu-west-1` — see the
   vpn-deploy README. The server picks it up on its next start.

3. **Fill in the template**: the device's private key and tunnel IP, the server
   public key, and your VPN DNS name as the endpoint.

4. **Set the MTU** — it must match the `/vpn-wireguard/MTU` SSM parameter
   (default 1420). To find the optimal value, probe the path from your network
   with the tunnel *down*:

   ```sh
   ping -4 -M do -s 1472 -c 3 vpn.<your-domain>
   ```

   If that gets replies your path MTU is the full 1500 and 1420 is correct.
   Otherwise reduce `-s` until pings succeed and set
   `MTU = (largest working size + 28) - 80` in both the SSM parameter and each
   device config.

Keep `PersistentKeepalive = 25` — it holds the NAT mapping open on your home
router so the server can always reach the device.

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
