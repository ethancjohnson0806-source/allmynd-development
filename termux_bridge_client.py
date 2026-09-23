#!/usr/bin/env python3
"""Minimal client for termux_bridge.py using one authenticated JSONL request."""

from __future__ import annotations

import argparse
import json
import os
import socket
from pathlib import Path
from typing import Any

MAX_LINE_BYTES = 64 * 1024


def call(host: str, port: int, token: str, request: dict[str, Any], timeout: float = 8.0) -> dict[str, Any]:
    payload = dict(request)
    payload["token"] = token
    encoded = (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")
    if len(encoded) > MAX_LINE_BYTES:
        raise ValueError("request is too large")
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        sock.sendall(encoded)
        data = b""
        while not data.endswith(b"\n"):
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
            if len(data) > MAX_LINE_BYTES:
                raise ValueError("response is too large")
    response = json.loads(data.decode("utf-8"))
    if not isinstance(response, dict):
        raise ValueError("invalid bridge response")
    return response


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Call the local ALL MY'ND bridge")
    parser.add_argument("operation", choices=["ping", "speak", "learn", "status", "wants", "stance", "save"])
    parser.add_argument("text", nargs="?")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--token-file")
    args = parser.parse_args(argv)
    token = os.environ.get("ALLMYND_BRIDGE_TOKEN", "")
    if args.token_file:
        token = Path(args.token_file).read_text(encoding="utf-8").strip()
    request: dict[str, Any] = {"op": args.operation}
    if args.operation in {"speak", "learn"}:
        if not args.text:
            parser.error("text is required for speak and learn")
        request["text"] = args.text
    print(json.dumps(call(args.host, args.port, token, request), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
