from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from runtime_config import load_settings


AUDIO_SUFFIXES = {".mp3", ".m4a", ".wav"}
FISH_MAX_NEW_TOKENS = 1024
FISH_CHUNK_LENGTH = 100


class VoiceCloneError(RuntimeError):
    pass


def fish_config() -> dict[str, object]:
    settings = load_settings()
    root_value = settings.get("FISH_SPEECH_ROOT", "").strip()
    root = Path(root_value).expanduser().resolve() if root_value else Path.home() / "fish-speech"
    python_value = settings.get("FISH_SPEECH_PYTHON", "").strip()
    # Keep the virtualenv symlink intact. Resolving it points at the base interpreter
    # and silently drops the virtualenv's site-packages.
    python = Path(python_value).expanduser() if python_value else root / ".venv/bin/python"
    checkpoint_value = settings.get("FISH_SPEECH_CHECKPOINT", "").strip()
    checkpoint = (
        Path(checkpoint_value).expanduser().resolve()
        if checkpoint_value
        else root / "checkpoints/fish-speech-1.5"
    )
    device = settings.get("FISH_SPEECH_DEVICE", "mps" if sys.platform == "darwin" else "cuda").strip()
    generator = checkpoint / "firefly-gan-vq-fsq-8x1024-21hz-generator.pth"
    text_inference = root / "fish_speech/models/text2semantic/inference.py"
    vq_inference = root / "fish_speech/models/vqgan/inference.py"
    configured = all(path.exists() for path in (python, checkpoint, generator, text_inference, vq_inference))
    return {
        "root": root,
        "python": python,
        "checkpoint": checkpoint,
        "generator": generator,
        "text_inference": text_inference,
        "vq_inference": vq_inference,
        "device": device,
        "configured": configured,
    }


def engine_status() -> dict[str, object]:
    config = fish_config()
    return {
        "provider": "Fish Speech",
        "configured": bool(config["configured"]),
        "clone_enabled": bool(config["configured"]),
        "device": str(config["device"]),
        "sample_rule": "10 秒到 5 分钟，MP3/M4A/WAV，不超过 20 MB；需要对应逐字稿",
    }


def audio_probe(path: Path) -> dict[str, object]:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise VoiceCloneError(f"声音样本不存在：{path}")
    if path.suffix.lower() not in AUDIO_SUFFIXES:
        raise VoiceCloneError("声音样本仅支持 MP3、M4A、WAV")
    if path.stat().st_size > 20 * 1024 * 1024:
        raise VoiceCloneError("声音样本不能超过 20 MB")
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ],
        text=True,
        capture_output=True,
    )
    if result.returncode:
        raise VoiceCloneError("无法读取声音样本，请换一个清晰的音频文件")
    duration = float(result.stdout.strip())
    if not 10 <= duration <= 300:
        raise VoiceCloneError(f"声音样本需 10 秒到 5 分钟，当前 {duration:.1f} 秒")
    return {
        "path": str(path),
        "duration": duration,
        "bytes": path.stat().st_size,
        "format": path.suffix.lower().lstrip("."),
    }


def voice_id_for(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_-").lower()
    if not slug or not slug[0].isalpha():
        slug = "voice"
    return f"{slug}_{time.strftime('%Y%m%d_%H%M%S')}"


def _run(command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    result = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True)
    if result.returncode:
        detail = (result.stderr or result.stdout or "Fish Speech 执行失败")[-1800:]
        raise VoiceCloneError(detail)


def _fish_env(root: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(root)
    return env


def _device_args(device: str) -> list[str]:
    args = ["--device", device, "--no-compile"]
    if device != "cpu":
        args.append("--half")
    return args


def _encode_reference(sample: Path, profile_dir: Path, config: dict[str, object]) -> Path:
    preview_wav = profile_dir / "reference-preview.wav"
    _run(
        [
            str(config["python"]), str(config["vq_inference"]),
            "-i", str(sample), "-o", str(preview_wav),
            "--checkpoint-path", str(config["generator"]),
            "--device", str(config["device"]),
        ],
        env=_fish_env(Path(config["root"])),
    )
    prompt_tokens = preview_wav.with_suffix(".npy")
    if not prompt_tokens.is_file():
        raise VoiceCloneError("Fish Speech 没有生成声音参考特征")
    return prompt_tokens


def _make_preview(sample: Path, output: Path) -> None:
    _run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(sample),
            "-t", "12", "-af", "highpass=f=65,lowpass=f=11500,loudnorm=I=-16:TP=-1.5:LRA=8",
            "-codec:a", "libmp3lame", "-q:a", "3", str(output),
        ]
    )


def list_voice_profiles(voices_dir: Path) -> list[dict[str, object]]:
    profiles: list[dict[str, object]] = []
    for path in sorted(voices_dir.glob("*/profile.json")):
        try:
            profile = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        voice_id = str(profile.get("voice_id", path.parent.name))
        profile["id"] = f"fish:{voice_id}"
        profile["ready"] = (path.parent / str(profile.get("prompt_tokens", "prompt.npy"))).is_file()
        profiles.append(profile)
    return profiles


def clone_voice(
    sample: Path,
    name: str,
    voices_dir: Path,
    reference_text: str,
) -> dict[str, object]:
    config = fish_config()
    if not config["configured"]:
        raise VoiceCloneError(
            "Fish Speech 未配置。请设置 FISH_SPEECH_ROOT、FISH_SPEECH_PYTHON 和 FISH_SPEECH_CHECKPOINT。"
        )
    sample_info = audio_probe(sample)
    reference_text = reference_text.strip()
    if len(reference_text) < 8:
        raise VoiceCloneError("请填写声音样本对应的逐字稿，至少 8 个字")
    voice_id = voice_id_for(name)
    profile_dir = voices_dir / voice_id
    profile_dir.mkdir(parents=True, exist_ok=False)
    try:
        reference = profile_dir / f"reference{sample.suffix.lower()}"
        shutil.copy2(sample, reference)
        prompt_tokens = _encode_reference(reference, profile_dir, config)
        preview = profile_dir / "preview.mp3"
        _make_preview(reference, preview)
        profile = {
            "voice_id": voice_id,
            "name": name.strip() or "我的克隆音色",
            "provider": "Fish Speech",
            "created_at": time.time(),
            "reference_audio": reference.name,
            "reference_text": reference_text,
            "prompt_tokens": prompt_tokens.name,
            "sample": sample_info,
            "preview": preview.name,
        }
        (profile_dir / "profile.json").write_text(
            json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    except Exception:
        shutil.rmtree(profile_dir, ignore_errors=True)
        raise
    return {**profile, "id": f"fish:{voice_id}", "ready": True}


def synthesize_fish(text: str, voice_id: str, output: Path, voices_dir: Path | None = None) -> Path:
    config = fish_config()
    if not config["configured"]:
        raise VoiceCloneError("Fish Speech 配音引擎未配置")
    voices_dir = voices_dir or Path(__file__).resolve().parent / "voices"
    profile_dir = (voices_dir / voice_id).resolve()
    if voices_dir.resolve() not in profile_dir.parents:
        raise VoiceCloneError("声音 ID 无效")
    profile_path = profile_dir / "profile.json"
    if not profile_path.is_file():
        raise VoiceCloneError("找不到 Fish Speech 声音档案")
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    prompt_tokens = profile_dir / str(profile["prompt_tokens"])
    reference_text = str(profile["reference_text"]).strip()
    if not prompt_tokens.is_file() or not reference_text:
        raise VoiceCloneError("Fish Speech 声音档案不完整")

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="fish-speech-", dir=output.parent) as temp_value:
        temp = Path(temp_value)
        semantic_dir = temp / "semantic"
        semantic_dir.mkdir()
        decoded = temp / "decoded.wav"
        _run(
            [
                str(config["python"]), str(config["text_inference"]),
                "--text", text,
                "--prompt-text", reference_text,
                "--prompt-tokens", str(prompt_tokens),
                "--checkpoint-path", str(config["checkpoint"]),
                "--num-samples", "1",
                # Fish 1.5 normally stops on its end token. A bounded ceiling keeps
                # a malformed/non-ending segment from running for hours on MPS.
                "--max-new-tokens", str(FISH_MAX_NEW_TOKENS),
                "--top-p", "0.7",
                "--repetition-penalty", "1.5",
                "--temperature", "0.7",
                "--seed", "42",
                *_device_args(str(config["device"])),
                "--iterative-prompt", "--chunk-length", str(FISH_CHUNK_LENGTH),
                "--output-dir", str(semantic_dir),
            ],
            env=_fish_env(Path(config["root"])),
        )
        codes = semantic_dir / "codes_0.npy"
        if not codes.is_file():
            raise VoiceCloneError("Fish Speech 没有生成语义特征")
        _run(
            [
                str(config["python"]), str(config["vq_inference"]),
                "-i", str(codes), "-o", str(decoded),
                "--checkpoint-path", str(config["generator"]),
                "--device", str(config["device"]),
            ],
            env=_fish_env(Path(config["root"])),
        )
        if not decoded.is_file():
            raise VoiceCloneError("Fish Speech 没有生成音频")
        _run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(decoded),
                "-af", "highpass=f=65,lowpass=f=11500,acompressor=threshold=-18dB:ratio=2.2:attack=12:release=160,loudnorm=I=-16:TP=-1.5:LRA=8,aresample=48000",
                str(output),
            ]
        )
    if not output.is_file() or output.stat().st_size < 1024:
        raise VoiceCloneError("Fish Speech 配音输出无效")
    return output
