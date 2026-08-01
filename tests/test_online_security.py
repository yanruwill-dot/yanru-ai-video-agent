import json
import uuid
import threading
import unittest
import urllib.error
import urllib.request

import app


class OnlineSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous_key = app.API_KEY
        app.API_KEY = "test-online-key"
        cls.server = app.ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.origin = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        app.API_KEY = cls.previous_key

    def test_health_rejects_missing_key(self):
        with self.assertRaises(urllib.error.HTTPError) as raised:
            urllib.request.urlopen(f"{self.origin}/api/health")
        self.assertEqual(raised.exception.code, 401)

    def test_health_accepts_header_key(self):
        request = urllib.request.Request(
            f"{self.origin}/api/health",
            headers={"X-Video-Agent-Key": "test-online-key"},
        )
        with urllib.request.urlopen(request) as response:
            payload = json.load(response)
        self.assertTrue(payload["ok"])

    def test_health_accepts_query_key_for_media_elements(self):
        with urllib.request.urlopen(
            f"{self.origin}/api/health?key=test-online-key"
        ) as response:
            payload = json.load(response)
        self.assertTrue(payload["ok"])

    def test_github_origin_preflight_allows_key_header(self):
        request = urllib.request.Request(
            f"{self.origin}/api/generate",
            method="OPTIONS",
            headers={
                "Origin": app.GITHUB_PAGES_ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,x-video-agent-key",
            },
        )
        with urllib.request.urlopen(request) as response:
            self.assertEqual(response.status, 204)
            self.assertEqual(
                response.headers["Access-Control-Allow-Origin"],
                app.GITHUB_PAGES_ORIGIN,
            )
            self.assertIn(
                "X-Video-Agent-Key",
                response.headers["Access-Control-Allow-Headers"],
            )

    def test_miniapp_multipart_video_upload(self):
        boundary = f"----CodexMiniapp{uuid.uuid4().hex}"
        payload = b"fake-video-bytes"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="sample.mp4"\r\n'
            "Content-Type: video/mp4\r\n\r\n"
        ).encode() + payload + f"\r\n--{boundary}--\r\n".encode()
        request = urllib.request.Request(
            f"{self.origin}/api/upload-file?name=sample.mp4",
            method="POST",
            data=body,
            headers={
                "X-Video-Agent-Key": "test-online-key",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
        )
        with urllib.request.urlopen(request) as response:
            result = json.load(response)
        path = app.Path(result["path"])
        try:
            self.assertEqual(path.read_bytes(), payload)
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
