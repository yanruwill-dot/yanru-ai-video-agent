import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from pipeline import (
    AUDIO_NORMALIZATION,
    EDIT_STYLES,
    MOTION_PRESETS,
    OUTPUT_AUDIO_RATE,
    PipelineError,
    caption_animation_filter,
    caption_overlay,
    keep_intervals,
    motion_filter,
    split_script,
    timeline_for,
    write_srt,
)
from voice_clone import (
    FISH_CHUNK_LENGTH,
    FISH_MAX_NEW_TOKENS,
    VoiceCloneError,
    audio_probe,
    fish_config,
    list_voice_profiles,
    voice_id_for,
)


class PipelineUnitTests(unittest.TestCase):
    def test_fish_generation_has_bounded_segment_budget(self):
        self.assertEqual(FISH_CHUNK_LENGTH, 100)
        self.assertEqual(FISH_MAX_NEW_TOKENS, 1024)

    def test_audio_is_normalized_for_social_video(self):
        self.assertIn("I=-16", AUDIO_NORMALIZATION)
        self.assertIn("TP=-1.5", AUDIO_NORMALIZATION)
        self.assertEqual(OUTPUT_AUDIO_RATE, "48000")

    def test_split_script_preserves_content(self):
        text = "第一句话很重要。第二句话继续解释！最后给行动。"
        lines = split_script(text, max_chars=9)
        self.assertGreaterEqual(len(lines), 3)
        self.assertEqual("".join(lines), text)

    def test_keep_intervals_removes_middle_silence_with_margin(self):
        intervals = keep_intervals(10.0, [(2.0, 4.0), (7.0, 8.0)], margin=0.2)
        self.assertEqual(intervals, [(0.0, 2.2), (3.8, 7.2), (7.8, 10.0)])

    def test_timeline_covers_full_duration(self):
        timeline = timeline_for(["短句", "这是一句更长的话"], 12.5)
        self.assertEqual(timeline[0]["start"], 0)
        self.assertAlmostEqual(timeline[-1]["end"], 12.5)
        self.assertLess(timeline[0]["end"], timeline[1]["end"])

    def test_srt_written_with_valid_timecodes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "captions.srt"
            write_srt([{"index": 1, "start": 0.0, "end": 1.25, "text": "测试字幕"}], path)
            content = path.read_text(encoding="utf-8")
            self.assertIn("00:00:00,000 --> 00:00:01,250", content)
            self.assertIn("测试字幕", content)

    def test_every_motion_skill_builds_a_filter(self):
        for preset in MOTION_PRESETS:
            value = motion_filter(preset)
            self.assertIn("scale=1080:1920", value)
        self.assertIn("zoompan", motion_filter("smart_push"))
        self.assertNotIn("zoompan", motion_filter("none"))

    def test_unknown_motion_skill_is_rejected(self):
        with self.assertRaises(PipelineError):
            motion_filter("fake-effect")

    def test_every_editing_style_renders_a_full_frame_caption(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as directory:
            for style in EDIT_STYLES:
                path = Path(directory) / f"{style}.png"
                caption_overlay("老板要的是AI获客结果", path, style)
                self.assertTrue(path.is_file())
                with Image.open(path) as image:
                    self.assertEqual(image.size, (1080, 1920))

    def test_big_text_styles_have_real_entry_animation(self):
        for style in ("jianying_big", "keyword_punch"):
            chain, x, y = caption_animation_filter(2, style, 1.25, "caption2")
            self.assertIn("scale=", chain)
            self.assertIn("fade=", chain)
            self.assertEqual(x, "(W-w)/2")
            self.assertEqual(y, "(H-h)/2")

    def test_unknown_editing_style_is_rejected(self):
        with self.assertRaises(PipelineError):
            caption_animation_filter(2, "fake-style", 0, "caption2")

    def test_clone_voice_id_is_provider_safe(self):
        value = voice_id_for("我的 专属 音色")
        self.assertRegex(value, r"^[A-Za-z][A-Za-z0-9_-]{7,}$")

    def test_short_clone_sample_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            sample = Path(directory) / "short.wav"
            import subprocess
            subprocess.run(
                ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                 "-i", "sine=frequency=440:duration=1", str(sample)],
                check=True,
            )
            with self.assertRaises(VoiceCloneError):
                audio_probe(sample)

    def test_fish_config_keeps_virtualenv_python_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "base-python"
            target.touch()
            link = root / "venv-python"
            link.symlink_to(target)
            checkpoint = root / "checkpoint"
            checkpoint.mkdir()
            (checkpoint / "firefly-gan-vq-fsq-8x1024-21hz-generator.pth").touch()
            (root / "fish_speech/models/text2semantic").mkdir(parents=True)
            (root / "fish_speech/models/text2semantic/inference.py").touch()
            (root / "fish_speech/models/vqgan").mkdir(parents=True)
            (root / "fish_speech/models/vqgan/inference.py").touch()
            with patch.dict("os.environ", {
                "FISH_SPEECH_ROOT": str(root),
                "FISH_SPEECH_PYTHON": str(link),
                "FISH_SPEECH_CHECKPOINT": str(checkpoint),
            }, clear=False):
                self.assertEqual(fish_config()["python"], link)

    def test_fish_config_prefers_explicit_mlx_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cli = root / ".venv/bin/fish-speech-mlx"
            cli.parent.mkdir(parents=True)
            cli.touch()
            with patch.dict("os.environ", {
                "FISH_SPEECH_BACKEND": "mlx",
                "FISH_SPEECH_MLX_ROOT": str(root),
                "FISH_SPEECH_MLX_MODEL": "local-test-model",
            }, clear=False):
                config = fish_config()
            self.assertEqual(config["backend"], "mlx")
            self.assertTrue(config["configured"])
            self.assertEqual(config["cli"], cli.resolve())

    def test_mlx_voice_profile_is_ready_without_pytorch_tokens(self):
        with tempfile.TemporaryDirectory() as directory:
            voices = Path(directory)
            profile_dir = voices / "owner_voice"
            profile_dir.mkdir()
            (profile_dir / "reference.wav").touch()
            (profile_dir / "profile.json").write_text(
                '{"voice_id":"owner_voice","backend":"mlx",'
                '"reference_audio":"reference.wav","reference_text":"授权参考逐字稿"}',
                encoding="utf-8",
            )
            profiles = list_voice_profiles(voices)
            self.assertEqual(len(profiles), 1)
            self.assertTrue(profiles[0]["ready"])


if __name__ == "__main__":
    unittest.main()
