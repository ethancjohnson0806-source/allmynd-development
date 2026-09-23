import json
import socket
import tempfile
import threading
import unittest
from pathlib import Path

from allmynd.bridge import Bridge
from termux_bridge import MAX_TEXT_CHARS, build_server

TOKEN = "test-token-" + ("x" * 40)


def request(port, payload):
    with socket.create_connection(("127.0.0.1", port), timeout=3) as sock:
        sock.sendall((json.dumps(payload) + "\n").encode())
        return json.loads(sock.makefile("rb").readline().decode())


class TermuxBridgeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        path = Path(self.directory.name) / "state.json"
        self.server = build_server("127.0.0.1", 0, Bridge(path=str(path)), TOKEN)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.directory.cleanup()

    def call(self, payload):
        payload = dict(payload)
        payload["token"] = TOKEN
        return request(self.port, payload)

    def test_ping_and_approved_operation(self):
        self.assertTrue(self.call({"op": "ping"})["ok"])
        result = self.call({"op": "speak", "text": "hello"})
        self.assertTrue(result["ok"])
        self.assertIsInstance(result["result"]["reply"], str)

    def test_wrong_token_is_rejected(self):
        result = request(self.port, {"op": "status", "token": "wrong"})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "unauthorized")

    def test_arbitrary_operation_is_rejected(self):
        result = self.call({"op": "execute", "command": "whoami"})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "operation is not allowed")

    def test_oversized_text_is_rejected(self):
        result = self.call({"op": "speak", "text": "x" * (MAX_TEXT_CHARS + 1)})
        self.assertFalse(result["ok"])
        self.assertIn("exceeds", result["error"])

    def test_non_loopback_bind_is_rejected(self):
        with self.assertRaises(ValueError):
            build_server("0.0.0.0", 0, Bridge(), TOKEN)


if __name__ == "__main__":
    unittest.main()
