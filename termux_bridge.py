#!/usr/bin/env python3
"""Authenticated, least-privilege JSONL bridge for a local ALL MY'ND process.

This is deliberately an IPC adapter, not a general-purpose MCP or remote shell.
It exposes only the stable operations needed by a client and never accepts paths,
Python, shell commands, or serialized objects from the wire.
"""

from __future__ import annotations

import argparse
import hmac
import json
import os
import secrets
import socketserver
import sys
import threading
from pathlib import Path
from typing import Any

from allmynd.bridge import Bridge

MAX_LINE_BYTES = 64 * 1024
MAX_TEXT_CHARS = 4_000
MAX_SOURCE_CHARS = 100
MIN_TOKEN_CHARS = 32
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


class BridgeProtocolError(Exception):
    """A client request was invalid or unauthorized."""


class BridgeService:
    """Thread-safe allowlisted operations over one in-memory Bridge."""

    def __init__(self, bridge: Bridge):
        self.bridge = bridge
        self.lock = threading.RLock()

    def dispatch(self, request: dict[str, Any]) -> dict[str, Any]:
        operation = request.get("op")
        if not isinstance(operation, str):
            raise BridgeProtocolError("missing operation")

        if operation == "ping":
            return {"ok": True, "result": {"service": "allmynd-bridge", "version": 1}}

        with self.lock:
            if operation == "speak":
                text = _bounded_text(request, "text", MAX_TEXT_CHARS)
                return {"ok": True, "result": {"reply": self.bridge.speak(text)}}
            if operation == "learn":
                text = _bounded_text(request, "text", MAX_TEXT_CHARS)
                source = request.get("source", "bridge-client")
                if not isinstance(source, str) or len(source) > MAX_SOURCE_CHARS:
                    raise BridgeProtocolError("source is invalid or too long")
                learned = self.bridge.learn(text, source=source)
                self.bridge.save()
                return {"ok": True, "result": {"learned_words": learned}}
            if operation == "status":
                return {"ok": True, "result": {"status": self.bridge.status()}}
            if operation == "wants":
                return {"ok": True, "result": {"wants": self.bridge.wants()}}
            if operation == "stance":
                return {"ok": True, "result": self.bridge.stance()}
            if operation == "save":
                self.bridge.save()
                return {"ok": True, "result": {"saved": True}}

        raise BridgeProtocolError("operation is not allowed")


def _bounded_text(request: dict[str, Any], key: str, limit: int) -> str:
    value = request.get(key)
    if not isinstance(value, str) or not value.strip():
        raise BridgeProtocolError(f"{key} must be non-empty text")
    if len(value) > limit:
        raise BridgeProtocolError(f"{key} exceeds {limit} characters")
    return value.strip()


def _read_token(token_file: str | None) -> str:
    value = os.environ.get("ALLMYND_BRIDGE_TOKEN", "")
    if token_file:
        value = Path(token_file).read_text(encoding="utf-8").strip()
    if len(value) < MIN_TOKEN_CHARS:
        raise SystemExit(
            "Set ALLMYND_BRIDGE_TOKEN or --token-file to a random token "
            f"of at least {MIN_TOKEN_CHARS} characters."
        )
    return value


class BridgeTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = False
    daemon_threads = True

    def __init__(self, address, handler_class, service, token):
        self.service = service
        self.token = token
        super().__init__(address, handler_class)


class RequestHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        self.connection.settimeout(5.0)
        raw = self.rfile.readline(MAX_LINE_BYTES + 1)
        if len(raw) > MAX_LINE_BYTES:
            self._reply({"ok": False, "error": "request too large"})
            return
        try:
            request = json.loads(raw.decode("utf-8"))
            if not isinstance(request, dict):
                raise BridgeProtocolError("request must be a JSON object")
            supplied = request.pop("token", None)
            if not isinstance(supplied, str) or not hmac.compare_digest(
                supplied, self.server.token
            ):
                raise BridgeProtocolError("unauthorized")
            response = self.server.service.dispatch(request)
        except (UnicodeDecodeError, json.JSONDecodeError):
            response = {"ok": False, "error": "invalid JSON"}
        except BridgeProtocolError as exc:
            response = {"ok": False, "error": str(exc)}
        except Exception:
            # Do not send tracebacks or internal state to clients.
            response = {"ok": False, "error": "internal bridge error"}
        self._reply(response)

    def _reply(self, response: dict[str, Any]) -> None:
        encoded = (json.dumps(response, separators=(",", ":")) + "\n").encode("utf-8")
        self.wfile.write(encoded)


def build_server(host: str, port: int, bridge: Bridge, token: str) -> BridgeTCPServer:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError(
            "Refusing non-loopback bind. Use an SSH tunnel for remote access; "
            "a network-facing TLS deployment needs a separate reviewed design."
        )
    return BridgeTCPServer((host, port), RequestHandler, BridgeService(bridge), token)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ALL MY'ND authenticated local IPC bridge")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--save", default="allmynd_v1.json")
    parser.add_argument("--token-file")
    args = parser.parse_args(argv)
    token = _read_token(args.token_file)
    bridge = Bridge(path=args.save)
    server = build_server(args.host, args.port, bridge, token)
    print(f"ALL MY'ND bridge listening on {args.host}:{args.port}", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
        with server.service.lock:
            bridge.save()
    return 0


if __name__ == "__main__":
    sys.exit(main())
