"""Bulk endpoints against a local fake API (the sandbox key does not work on bulk)."""
import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from easyemailverification import Client, EEVError

STATE = {"polls": 0, "uploaded": b"", "ctype": ""}


class FakeAPI(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body.encode() if isinstance(body, str) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _route(self):
        if self.headers.get("X-API-Key") != "live_key":
            return self._send(401, {"status": "error", "message": "Invalid API key"})
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n) if n else b""
        if self.command == "POST" and self.path == "/bulk/upload":
            STATE["uploaded"], STATE["ctype"] = body, self.headers.get("Content-Type", "")
            return self._send(200, {"status": "accepted", "list_id": "abc123", "filename": "leads.csv", "uploaded": 2, "message": "ok"})
        if self.path == "/bulk/status/abc123":
            STATE["polls"] += 1
            done = STATE["polls"] >= 2
            return self._send(200, {"list_id": "abc123", "status": "completed" if done else "processing", "progress": 100 if done else 50})
        if self.path == "/bulk/status":
            return self._send(200, {"status": "ok", "total_lists": 1, "lists": []})
        if self.path == "/bulk/download/abc123":
            return self._send(200, "Email,Result\na@example.com,valid\n", "text/plain")
        if self.command == "DELETE" and self.path == "/bulk/abc123":
            return self._send(200, {"status": "deleted", "list_id": "abc123", "message": "deleted"})
        self._send(404, {"status": "error", "message": "Not found"})

    do_GET = do_POST = do_DELETE = _route


class BulkTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), FakeAPI)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.eev = Client("live_key", base_url="http://127.0.0.1:%d" % cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_upload_from_path(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "leads.csv")
            with open(path, "w") as f:
                f.write("a@example.com\nb@example.com\n")
            r = self.eev.bulk.upload(path)
        self.assertEqual(r["list_id"], "abc123")
        self.assertIn("multipart/form-data", STATE["ctype"])
        self.assertIn(b'filename="leads.csv"', STATE["uploaded"])
        self.assertIn(b"b@example.com", STATE["uploaded"])

    def test_upload_from_bytes(self):
        self.assertEqual(self.eev.bulk.upload(b"a@example.com\n", filename="x.csv")["status"], "accepted")

    def test_wait_list_download_delete(self):
        STATE["polls"] = 0
        self.assertEqual(self.eev.bulk.wait("abc123", interval=0.01)["status"], "completed")
        self.assertEqual(self.eev.bulk.list()["total_lists"], 1)
        self.assertTrue(self.eev.bulk.download("abc123").startswith("Email,Result"))
        self.assertEqual(self.eev.bulk.delete("abc123")["status"], "deleted")

    def test_errors(self):
        with self.assertRaises(EEVError) as ctx:
            self.eev.bulk.status("nope")
        self.assertEqual((ctx.exception.status, ctx.exception.message), (404, "Not found"))


if __name__ == "__main__":
    unittest.main()
