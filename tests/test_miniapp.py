import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MINIAPP = ROOT / "miniprogram"


class MiniAppTests(unittest.TestCase):
    def test_native_miniapp_project_is_complete(self):
        required = [
            "app.js",
            "app.json",
            "app.wxss",
            "project.config.json",
            "sitemap.json",
            "pages/studio/index.js",
            "pages/studio/index.json",
            "pages/studio/index.wxml",
            "pages/studio/index.wxss",
            "utils/api.js",
        ]
        for relative in required:
            self.assertTrue((MINIAPP / relative).is_file(), relative)

    def test_app_route_and_project_config_are_valid_json(self):
        app = json.loads((MINIAPP / "app.json").read_text(encoding="utf-8"))
        project = json.loads((MINIAPP / "project.config.json").read_text(encoding="utf-8"))
        self.assertIn("pages/studio/index", app["pages"])
        self.assertEqual(project["compileType"], "miniprogram")
        self.assertEqual(project["miniprogramRoot"], "./")

    def test_miniapp_is_native_not_webview_wrapper(self):
        markup = (MINIAPP / "pages" / "studio" / "index.wxml").read_text(encoding="utf-8")
        script = (MINIAPP / "pages" / "studio" / "index.js").read_text(encoding="utf-8")
        api_script = (MINIAPP / "utils" / "api.js").read_text(encoding="utf-8")
        self.assertNotIn("<web-view", markup)
        self.assertIn("wx.chooseMedia", script)
        self.assertIn("wx.chooseMessageFile", script)
        self.assertIn("wx.uploadFile", api_script)
        self.assertNotIn("readFile", api_script)
        self.assertIn('this.submit("generate"', script)
        self.assertIn("saveVideoToPhotosAlbum", script)
        self.assertIn("Fish Speech", markup)
        self.assertIn("searchKnowledge", script)

    def test_miniapp_reuses_authenticated_backend_api(self):
        api_script = (MINIAPP / "utils" / "api.js").read_text(encoding="utf-8")
        self.assertIn("X-Video-Agent-Key", api_script)
        self.assertIn('name: "file"', api_script)
        self.assertIn("https:\\/\\/", api_script)
        self.assertIn("/runs/", api_script)


if __name__ == "__main__":
    unittest.main()
