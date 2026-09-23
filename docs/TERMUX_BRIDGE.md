# Termux bridge

This repository includes a deliberately small authenticated JSONL bridge for connecting a local client to ALL MY'ND. It is **not** a remote shell, Python evaluator, generic MCP server, or LAN-discovery service.

## What it exposes

The allowlist contains only `ping`, `speak`, `learn`, `status`, `wants`, `stance`, and `save`. Requests are size-limited, token-authenticated, serialized as one JSON object per line, and handled by one in-memory `Bridge`. The save path is selected by the server process and cannot be supplied by a client.

The server refuses non-loopback binds. That is intentional. For access from another computer, use an SSH tunnel rather than exposing an unauthenticated phone port to Wi-Fi.

## Termux setup

On the phone, install Python and OpenSSH in Termux, then clone this public repository:

```bash
pkg update
pkg install python openssh git
python -m pip install numpy
git clone https://github.com/ethancjohnson0806-source/allmynd-development.git
cd allmynd-development
```

Create a token outside the repository. It must be random and at least 32 characters:

```bash
python - <<'PY' > "$HOME/.allmynd-bridge-token"
import secrets
print(secrets.token_urlsafe(48))
PY
chmod 600 "$HOME/.allmynd-bridge-token"
```

Start the bridge on the phone’s loopback interface:

```bash
python termux_bridge.py --token-file "$HOME/.allmynd-bridge-token"
```

The live save file remains on the phone and is excluded from Git.

## SSH tunnel from another computer

First, make SSH reachable on the phone and determine the phone’s LAN address. From the other computer, forward a local port to the phone’s loopback bridge:

```bash
ssh -N -L 8765:127.0.0.1:8765 USER@PHONE_LAN_IP
```

Keep that terminal open. In a second terminal, copy the token securely to the client machine; do not paste it into GitHub, chat, or the command history. Then call the bridge through the local end of the tunnel:

```bash
export ALLMYND_BRIDGE_TOKEN="$(cat ~/.allmynd-bridge-token)"
python termux_bridge_client.py ping
python termux_bridge_client.py speak "hello from the other computer"
python termux_bridge_client.py status
```

The client still connects to `127.0.0.1`; SSH carries the encrypted connection to the phone. For a phone-only workflow, run `termux_bridge_client.py` locally against the same loopback port.

## Safety rules

- Do not pass `--host 0.0.0.0`; the server rejects non-loopback binds.
- Do not store the token in the repository, a shell script committed to Git, screenshots, or a public issue.
- Use a separate SSH account or key with the smallest practical access. Never forward SSH agent credentials to the phone.
- Stop the server with Ctrl-C when it is not needed. It saves state during clean shutdown.
- The bridge does not provide TLS itself; SSH is the transport boundary for remote access.
- This protocol is intentionally not MCP-compatible yet. An MCP adapter can be added later around this allowlist after testing authentication, replay behavior, and lifecycle management.

## Troubleshooting

`unauthorized` means the client and server tokens differ. `connection refused` usually means the server is not running, the SSH tunnel is closed, or the port numbers differ. If NumPy cannot be installed on the phone, stop there rather than changing the engine’s numerical implementation; use the project’s existing supported Python environment or resolve the Termux package issue separately.
