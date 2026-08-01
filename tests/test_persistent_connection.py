import plistlib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PersistentConnectionTests(unittest.TestCase):
    def test_github_page_falls_back_to_persistent_local_engine(self):
        script = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn('const LOCAL_ENGINE_ORIGIN = "http://127.0.0.1:8788"', script)
        self.assertIn("location.hostname.endsWith(\"github.io\")", script)
        self.assertIn("? LOCAL_ENGINE_ORIGIN", script)

    def test_launch_agent_runs_at_login_and_restarts_engine(self):
        template = ROOT / "launcher" / "com.yanru.video-agent.plist"
        with template.open("rb") as stream:
            payload = plistlib.load(stream)
        self.assertEqual(payload["Label"], "com.yanru.video-agent")
        self.assertTrue(payload["RunAtLoad"])
        self.assertTrue(payload["KeepAlive"])
        self.assertIn("--port", payload["ProgramArguments"])
        self.assertIn("8788", payload["ProgramArguments"])


if __name__ == "__main__":
    unittest.main()
