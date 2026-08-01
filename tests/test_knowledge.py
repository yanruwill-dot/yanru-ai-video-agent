import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from knowledge import KnowledgeError, search_getnote, search_knowledge, search_obsidian


class KnowledgeTests(unittest.TestCase):
    def test_obsidian_search_returns_traceable_markdown_result(self):
        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory)
            (vault / "视频智能体.md").write_text(
                "Fish Speech 配音后，FFmpeg 自动生成字幕和成片。", encoding="utf-8"
            )
            (vault / "无关.md").write_text("今天去散步。", encoding="utf-8")
            rows = search_obsidian(vault, "Fish Speech 自动成片", limit=3)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["source"], "obsidian")
            self.assertTrue(str(rows[0]["path"]).endswith("视频智能体.md"))

    def test_missing_vault_is_reported_without_hiding_getnote_boundary(self):
        with patch("knowledge.search_getnote", side_effect=KnowledgeError("未登录")):
            result = search_knowledge("视频智能体", vault="/missing", limit=2)
        self.assertEqual(result["results"], [])
        self.assertEqual({item["source"] for item in result["errors"]}, {"obsidian", "getnote"})

    @patch("knowledge.shutil.which", return_value="/usr/local/bin/getnote")
    @patch("knowledge.subprocess.run")
    def test_getnote_ids_are_strings_and_duplicate_snippets_are_removed(self, run, _which):
        run.return_value.returncode = 0
        run.return_value.stdout = json.dumps({
            "success": True,
            "data": {"results": [
                {"note_id": 1234567890123456789, "title": "A", "content": "同一片段"},
                {"note_id": 1234567890123456789, "title": "A", "content": "同一片段"},
            ]},
        })
        run.return_value.stderr = ""
        rows = search_getnote("视频", 5)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["note_id"], "1234567890123456789")


if __name__ == "__main__":
    unittest.main()
