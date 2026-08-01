import unittest
from pathlib import Path

from pipeline import EDIT_STYLES


ROOT = Path(__file__).resolve().parents[1]


class AppleEditingUITests(unittest.TestCase):
    def test_motion_skill_panel_is_removed(self):
        html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("动效 Skill", html)
        self.assertNotIn('id="motionGrid"', html)

    def test_advanced_jianying_and_kaipai_templates_exist(self):
        expected = {
            "jianying_big",
            "jianying_clean",
            "keyword_punch",
            "kaipai_talk",
            "kaipai_boss",
            "kaipai_story",
        }
        self.assertTrue(expected.issubset(EDIT_STYLES))

    def test_motion_is_derived_from_editing_template(self):
        script = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("MOTION_BY_STYLE", script)
        self.assertNotIn('input[name="motion"]', script)
        self.assertIn("yanru-ai-video-agent/releases", script)

    def test_layout_does_not_force_desktop_width(self):
        css = (ROOT / "static" / "styles.css").read_text(encoding="utf-8")
        self.assertNotIn("min-width: 1180px", css)
        self.assertIn(".column:last-child .launch-panel", css)
        self.assertNotIn(".column:last-child { grid-column: 1 / -1; display: grid; grid-template-columns: repeat(3, 1fr); }", css)

    def test_static_assets_are_cache_busted(self):
        html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        self.assertIn("./styles.css?v=2.0.0", html)
        self.assertIn("./app.js?v=2.0.0", html)

    def test_mobile_workbench_has_native_touch_navigation_and_connection_sheet(self):
        html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        css = (ROOT / "static" / "styles.css").read_text(encoding="utf-8")
        script = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn('class="mobile-dock"', html)
        self.assertIn('id="mobileGenerateBtn"', html)
        self.assertIn('id="connectionSheet"', html)
        self.assertIn("env(safe-area-inset-bottom)", css)
        self.assertIn("font-size: 16px", css)
        self.assertIn('localStorage.setItem("video-agent-api"', script)
        self.assertIn("isAllowedConnectionOrigin", script)

    def test_public_workbench_uses_fish_and_has_knowledge_connectors(self):
        html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("Fish Speech", html)
        self.assertNotIn("Moss", html)
        self.assertNotIn("MiniMax", html)
        self.assertIn('id="knowledgeQuery"', html)
        self.assertIn('/api/knowledge/search', script)


if __name__ == "__main__":
    unittest.main()
