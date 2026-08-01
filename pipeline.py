#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
from voice_clone import VoiceCloneError, synthesize_fish


FONT_CANDIDATES = [
    Path(os.environ.get("VIDEO_AGENT_FONT", "")),
    Path("/System/Library/Fonts/Hiragino Sans GB.ttc"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
]
FONT = next((path for path in FONT_CANDIDATES if str(path) and path.is_file()), FONT_CANDIDATES[1])
VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}


class PipelineError(RuntimeError):
    pass


def run(command: list[str], log_path: Path | None = None, capture: bool = False) -> subprocess.CompletedProcess:
    if log_path:
        with log_path.open("a", encoding="utf-8") as log:
            log.write("$ " + " ".join(command) + "\n")
    result = subprocess.run(command, text=True, capture_output=True)
    if log_path:
        with log_path.open("a", encoding="utf-8") as log:
            if result.stdout:
                log.write(result.stdout + "\n")
            if result.stderr:
                log.write(result.stderr + "\n")
    if result.returncode:
        detail = (result.stderr or result.stdout or "命令执行失败")[-1600:]
        raise PipelineError(detail)
    return result


def validate_source(path_text: str) -> Path:
    path = Path(path_text).expanduser().resolve()
    if not path.is_file():
        raise PipelineError(f"素材不存在：{path}")
    if path.suffix.lower() not in VIDEO_SUFFIXES:
        raise PipelineError("仅支持常见视频格式：MP4、MOV、M4V、AVI、MKV、WEBM")
    return path


def probe(path: Path) -> dict:
    result = run([
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration,size,bit_rate:stream=index,codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels",
        "-of", "json", str(path)
    ], capture=True)
    return json.loads(result.stdout)


def duration_of(path: Path) -> float:
    return float(probe(path)["format"]["duration"])


def has_audio(path: Path) -> bool:
    return any(stream.get("codec_type") == "audio" for stream in probe(path).get("streams", []))


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(FONT), size=size, index=1 if bold else 0)
    except OSError:
        return ImageFont.truetype(str(FONT), size=size)


def split_script(text: str, max_chars: int = 18) -> list[str]:
    clean = re.sub(r"\s+", "", text.strip())
    if not clean:
        raise PipelineError("口播文案不能为空")
    pieces = [part for part in re.split(r"(?<=[。！？!?；;])", clean) if part]
    lines: list[str] = []
    for piece in pieces:
        while len(piece) > max_chars:
            lines.append(piece[:max_chars])
            piece = piece[max_chars:]
        if piece:
            lines.append(piece)
    return lines


def timeline_for(lines: list[str], duration: float) -> list[dict]:
    weights = [max(len(line), 4) for line in lines]
    total = sum(weights)
    cursor = 0.0
    result = []
    for index, (line, weight) in enumerate(zip(lines, weights), 1):
        segment_duration = duration * weight / total
        end = duration if index == len(lines) else cursor + segment_duration
        result.append({"index": index, "start": cursor, "end": end, "text": line})
        cursor = end
    return result


def srt_time(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    secs, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def write_srt(timeline: list[dict], path: Path) -> None:
    blocks = []
    for item in timeline:
        blocks.append(
            f"{item['index']}\n{srt_time(item['start'])} --> {srt_time(item['end'])}\n{item['text']}\n"
        )
    path.write_text("\n".join(blocks), encoding="utf-8")


def synthesize_voice(text: str, voice: str, out_dir: Path, log: Path) -> Path:
    if voice.startswith("fish:"):
        _, voice_id = voice.split(":", 1)
        media = out_dir / "voice.wav"
        try:
            return synthesize_fish(text, voice_id, media)
        except VoiceCloneError as error:
            raise PipelineError(str(error)) from error
    edge_tts = shutil.which("edge-tts")
    if edge_tts:
        media = out_dir / "voice.mp3"
        try:
            run([edge_tts, "--voice", voice, "--text", text, "--write-media", str(media)], log)
            if media.exists() and media.stat().st_size > 1024:
                return media
        except PipelineError:
            pass
    aiff = out_dir / "voice.aiff"
    mac_voice = "Tingting" if "Xiaoxiao" in voice or "Yunxi" in voice else "Sinji"
    run(["say", "-v", mac_voice, "-o", str(aiff), text], log)
    return aiff


MOTION_PRESETS = {
    "none": {
        "name": "稳重原片",
        "description": "不加镜头运动，适合正式口播",
    },
    "smart_push": {
        "name": "智能轻推镜",
        "description": "持续缓慢推进，强化人物聚焦",
    },
    "breath_focus": {
        "name": "呼吸聚焦",
        "description": "轻微缩放往复，保持画面活力",
    },
    "beat_impact": {
        "name": "节奏冲击",
        "description": "周期性快速推近再回弹，适合强钩子",
    },
}

EDIT_STYLES = {
    "classic": {
        "name": "经典口播",
        "description": "稳重底栏字幕，适合正式讲解",
        "max_chars": 18,
    },
    "jianying_big": {
        "name": "剪映经典·大字弹跳",
        "description": "超大白字、黑描边、重点黄字和快速弹入",
        "max_chars": 8,
    },
    "jianying_clean": {
        "name": "剪映经典·清透标题",
        "description": "清透玻璃字幕、蓝色重点词和稳定轻推镜头",
        "max_chars": 12,
    },
    "kaipai_talk": {
        "name": "开拍·口播重点",
        "description": "单屏短句、重点色块和轻推入场",
        "max_chars": 10,
    },
    "kaipai_boss": {
        "name": "开拍·老板观点",
        "description": "观点型大字、暖色重点词和稳定人物聚焦",
        "max_chars": 9,
    },
    "kaipai_story": {
        "name": "开拍·故事叙述",
        "description": "电影感双行字幕、柔和暖白字和呼吸推镜",
        "max_chars": 14,
    },
    "keyword_punch": {
        "name": "卡点快切·冲击字幕",
        "description": "一屏一重点，大字冲击并跟随节奏变焦",
        "max_chars": 6,
    },
    "knowledge_highlight": {
        "name": "知识口播·关键词高亮",
        "description": "高信息密度字幕，自动强调业务关键词",
        "max_chars": 14,
    },
}

AUDIO_NORMALIZATION = "loudnorm=I=-16:TP=-1.5:LRA=11"


def motion_filter(preset: str) -> str:
    if preset not in MOTION_PRESETS:
        raise PipelineError(f"未知动效 Skill：{preset}")
    base = (
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,eq=brightness=-0.06:saturation=0.92"
    )
    if preset == "none":
        return base
    if preset == "smart_push":
        return base + ",zoompan=z='min(max(pzoom,1.0)+0.0008,1.10)':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s=1080x1920:fps=30"
    if preset == "breath_focus":
        return base + ",zoompan=z='1.035+0.02*sin(on/24)':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s=1080x1920:fps=30"
    return base + ",zoompan=z='if(lt(mod(on,72),9),1.09-0.01*mod(on,72),1.0)':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s=1080x1920:fps=30,vignette=PI/5"


def detect_silences(source: Path, threshold_db: int, min_silence: float, log: Path) -> list[tuple[float, float]]:
    result = subprocess.run([
        "ffmpeg", "-hide_banner", "-i", str(source), "-af",
        f"silencedetect=noise={threshold_db}dB:d={min_silence}", "-f", "null", "-"
    ], text=True, capture_output=True)
    with log.open("a", encoding="utf-8") as stream:
        stream.write(result.stderr + "\n")
    starts = [float(value) for value in re.findall(r"silence_start: ([0-9.]+)", result.stderr)]
    ends = [float(value) for value in re.findall(r"silence_end: ([0-9.]+)", result.stderr)]
    return list(zip(starts, ends))


def keep_intervals(duration: float, silences: list[tuple[float, float]], margin: float = 0.18) -> list[tuple[float, float]]:
    if not silences:
        return [(0.0, duration)]
    intervals = []
    cursor = 0.0
    for start, end in silences:
        keep_end = min(duration, start + margin)
        if keep_end - cursor >= 0.12:
            intervals.append((cursor, keep_end))
        cursor = max(0.0, end - margin)
    if duration - cursor >= 0.12:
        intervals.append((cursor, duration))
    merged: list[tuple[float, float]] = []
    for start, end in intervals:
        if merged and start - merged[-1][1] < 0.08:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    return merged


def auto_cut(source: Path, out_dir: Path, threshold_db: int = -35, min_silence: float = 0.65) -> tuple[Path, dict]:
    log = out_dir / "pipeline.log"
    output = out_dir / "auto-cut.mp4"
    if not has_audio(source):
        shutil.copy2(source, output)
        return output, {"silences": [], "keep_intervals": [[0, duration_of(source)]], "reason": "源视频没有音轨"}
    duration = duration_of(source)
    silences = detect_silences(source, threshold_db, min_silence, log)
    intervals = keep_intervals(duration, silences)
    if len(intervals) == 1 and intervals[0][0] == 0 and math.isclose(intervals[0][1], duration):
        shutil.copy2(source, output)
    else:
        filters = []
        concat_inputs = []
        for index, (start, end) in enumerate(intervals):
            filters.append(f"[0:v]trim=start={start:.3f}:end={end:.3f},setpts=PTS-STARTPTS[v{index}]")
            filters.append(f"[0:a]atrim=start={start:.3f}:end={end:.3f},asetpts=PTS-STARTPTS[a{index}]")
            concat_inputs.append(f"[v{index}][a{index}]")
        filters.append("".join(concat_inputs) + f"concat=n={len(intervals)}:v=1:a=1[v][a]")
        run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
            "-filter_complex", ";".join(filters), "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", "-movflags", "+faststart", str(output)
        ], log)
    report = {
        "source_duration": duration,
        "output_duration": duration_of(output),
        "silences": silences,
        "keep_intervals": intervals,
        "threshold_db": threshold_db,
        "min_silence": min_silence
    }
    (out_dir / "auto-cut.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return output, report


def wrap_caption(text: str, limit: int = 12) -> str:
    return "\n".join(text[index:index + limit] for index in range(0, len(text), limit))


def emphasis_term(text: str) -> str:
    candidates = (
        "人工智能", "自动化", "智能体", "获客", "成交", "客户", "老板", "赚钱",
        "结果", "流程", "内容", "效率", "成本", "增长", "AI",
    )
    for candidate in candidates:
        if candidate in text:
            return candidate
    clean = re.sub(r"[，。！？、,.!?；;：:\s]", "", text)
    return clean[-min(4, len(clean)):] if clean else ""


def draw_rich_line(
    draw: ImageDraw.ImageDraw,
    line: str,
    y: int,
    text_font: ImageFont.FreeTypeFont,
    accent: tuple[int, int, int, int],
    stroke_width: int,
) -> None:
    term = emphasis_term(line)
    start = line.find(term) if term else -1
    pieces = [(line, "white")] if start < 0 else [
        (line[:start], "white"),
        (term, accent),
        (line[start + len(term):], "white"),
    ]
    widths = [draw.textlength(piece, font=text_font) for piece, _ in pieces]
    x = (1080 - sum(widths)) / 2
    for (piece, fill), width in zip(pieces, widths):
        if piece:
            draw.text(
                (x, y), piece, font=text_font, fill=fill,
                stroke_width=stroke_width, stroke_fill=(0, 0, 0, 255),
            )
        x += width


def title_overlay(title: str, path: Path) -> None:
    canvas = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(
        (54, 64, 1026, 286),
        34,
        fill=(18, 18, 22, 218),
        outline=(255, 255, 255, 42),
        width=2,
    )
    draw.rounded_rectangle((86, 92, 220, 130), 19, fill=(10, 132, 255, 255))
    draw.text((108, 99), "AI VIDEO", font=font(19, True), fill="white")
    title_text = wrap_caption(title, 14)[:34]
    draw.multiline_text((86, 142), title_text, font=font(54, True), fill="white", spacing=4)
    canvas.save(path)


def caption_overlay(text: str, path: Path, editing_style: str = "classic") -> None:
    if editing_style not in EDIT_STYLES:
        raise PipelineError(f"未知剪辑模板：{editing_style}")
    canvas = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    if editing_style == "jianying_big":
        lines = [text[index:index + 8] for index in range(0, len(text), 8)][:2]
        text_font = font(108, True)
        y = 1120 - (len(lines) - 1) * 66
        for line in lines:
            draw_rich_line(draw, line, y, text_font, (255, 228, 64, 255), 10)
            y += 132
        canvas.save(path)
        return
    if editing_style == "kaipai_talk":
        lines = [text[index:index + 10] for index in range(0, len(text), 10)][:2]
        text_font = font(88, True)
        y = 1130 - (len(lines) - 1) * 54
        box_height = len(lines) * 108 + 54
        draw.rounded_rectangle((62, y - 24, 1018, y - 24 + box_height), 30, fill=(8, 10, 15, 205))
        for line in lines:
            draw_rich_line(draw, line, y, text_font, (68, 241, 218, 255), 6)
            y += 108
        canvas.save(path)
        return
    if editing_style == "jianying_clean":
        lines = [text[index:index + 12] for index in range(0, len(text), 12)][:2]
        text_font = font(76, True)
        y = 1350 - (len(lines) - 1) * 48
        draw.rounded_rectangle(
            (58, y - 28, 1022, y + len(lines) * 94 + 10),
            28,
            fill=(18, 20, 28, 188),
            outline=(255, 255, 255, 45),
            width=2,
        )
        for line in lines:
            draw_rich_line(draw, line, y, text_font, (84, 169, 255, 255), 4)
            y += 94
        canvas.save(path)
        return
    if editing_style == "kaipai_boss":
        lines = [text[index:index + 9] for index in range(0, len(text), 9)][:2]
        text_font = font(98, True)
        y = 1030 - (len(lines) - 1) * 60
        draw.rounded_rectangle((52, y - 28, 1028, y + len(lines) * 120 + 8), 22, fill=(4, 5, 8, 220))
        draw.rounded_rectangle((52, y - 28, 68, y + len(lines) * 120 + 8), 8, fill=(255, 159, 64, 255))
        for line in lines:
            draw_rich_line(draw, line, y, text_font, (255, 174, 76, 255), 7)
            y += 120
        canvas.save(path)
        return
    if editing_style == "kaipai_story":
        lines = [text[index:index + 14] for index in range(0, len(text), 14)][:2]
        text_font = font(66, True)
        y = 1450 - (len(lines) - 1) * 42
        draw.rounded_rectangle((72, y - 24, 1008, y + len(lines) * 82 + 8), 18, fill=(0, 0, 0, 165))
        for line in lines:
            draw_rich_line(draw, line, y, text_font, (255, 218, 164, 255), 3)
            y += 82
        canvas.save(path)
        return
    if editing_style == "keyword_punch":
        lines = [text[index:index + 6] for index in range(0, len(text), 6)][:2]
        text_font = font(132, True)
        y = 840 - (len(lines) - 1) * 80
        for line in lines:
            draw_rich_line(draw, line, y, text_font, (255, 62, 205, 255), 12)
            y += 160
        canvas.save(path)
        return
    if editing_style == "knowledge_highlight":
        lines = [text[index:index + 14] for index in range(0, len(text), 14)][:2]
        text_font = font(76, True)
        y = 1390 - (len(lines) - 1) * 48
        draw.rounded_rectangle((48, y - 26, 1032, y + len(lines) * 94 + 12), 26, fill=(0, 0, 0, 205))
        for line in lines:
            draw_rich_line(draw, line, y, text_font, (57, 238, 215, 255), 5)
            y += 94
        canvas.save(path)
        return
    wrapped = wrap_caption(text, 13)
    box = draw.multiline_textbbox((0, 0), wrapped, font=font(60, True), spacing=10, stroke_width=2)
    width = min(980, box[2] - box[0] + 84)
    height = box[3] - box[1] + 54
    x = (1080 - width) // 2
    y = 1540 - height
    draw.rounded_rectangle((x, y, x + width, y + height), 30, fill=(0, 0, 0, 196))
    draw.multiline_text(
        (540, y + 22), wrapped, anchor="ma", align="center", font=font(60, True),
        fill="white", spacing=10, stroke_width=2, stroke_fill=(0, 0, 0, 255)
    )
    canvas.save(path)


def caption_animation_filter(input_index: int, editing_style: str, start: float, label: str) -> tuple[str, str, str]:
    if editing_style not in EDIT_STYLES:
        raise PipelineError(f"未知剪辑模板：{editing_style}")
    source = f"[{input_index}:v]"
    if editing_style in {"jianying_big", "keyword_punch"}:
        scale = "if(lt(t,0.10),0.82+2.6*t,if(lt(t,0.18),1.08-(t-0.10),1))"
        chain = (
            f"{source}format=rgba,"
            f"scale=w='iw*{scale}':h='ih*{scale}':eval=frame,"
            f"fade=t=in:st=0:d=0.08:alpha=1,setpts=PTS-STARTPTS+{start:.3f}/TB[{label}]"
        )
        return chain, "(W-w)/2", "(H-h)/2"
    if editing_style in {"kaipai_talk", "kaipai_boss"}:
        chain = (
            f"{source}format=rgba,fade=t=in:st=0:d=0.14:alpha=1,"
            f"setpts=PTS-STARTPTS+{start:.3f}/TB[{label}]"
        )
        return chain, "0", f"if(lt(t-{start:.3f},0.18),30*(1-(t-{start:.3f})/0.18),0)"
    if editing_style in {"jianying_clean", "kaipai_story", "knowledge_highlight"}:
        chain = (
            f"{source}format=rgba,fade=t=in:st=0:d=0.10:alpha=1,"
            f"setpts=PTS-STARTPTS+{start:.3f}/TB[{label}]"
        )
        return chain, "0", "0"
    chain = f"{source}format=rgba,setpts=PTS-STARTPTS+{start:.3f}/TB[{label}]"
    return chain, "0", "0"


def make_contact_sheet(video: Path, output: Path) -> None:
    interval = max(duration_of(video) / 6, 0.5)
    run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video),
        "-vf", f"fps=1/{interval:.3f},scale=270:-1,tile=3x2:padding=8:margin=8:color=white",
        "-frames:v", "1", str(output)
    ])


def make_cover(video: Path, title: str, output: Path) -> None:
    frame = output.with_suffix(".frame.jpg")
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", "0.4", "-i", str(video), "-frames:v", "1", str(frame)])
    image = Image.open(frame).convert("RGB")
    image = ImageOps.fit(image, (1080, 1920), Image.Resampling.LANCZOS)
    image = ImageEnhance.Brightness(image).enhance(0.68)
    blurred = image.filter(ImageFilter.GaussianBlur(1.2))
    draw = ImageDraw.Draw(blurred)
    draw.rounded_rectangle((58, 180, 1022, 620), 42, fill=(4, 5, 10, 220), outline=(255, 51, 204), width=5)
    draw.text((96, 225), "AI 视频智能体", font=font(48, True), fill=(255, 61, 207))
    draw.multiline_text((96, 322), wrap_caption(title, 10), font=font(92, True), fill="white", spacing=14, stroke_width=2, stroke_fill="black")
    draw.rounded_rectangle((72, 1700, 1008, 1822), 28, fill=(46, 240, 220))
    draw.text((540, 1761), "原创脚本 · AI 配音 · 自动剪辑", anchor="mm", font=font(38, True), fill=(5, 8, 14))
    blurred.save(output, quality=94)


def render_video(
    source: Path,
    title: str,
    script: str,
    voice: str,
    out_dir: Path,
    use_auto_cut: bool = True,
    threshold_db: int = -35,
    min_silence: float = 0.65,
    motion_preset: str = "smart_push",
    editing_style: str = "classic",
    progress=None
) -> dict:
    def emit(value: int, message: str) -> None:
        if progress:
            progress(value, message)

    out_dir.mkdir(parents=True, exist_ok=True)
    log = out_dir / "pipeline.log"
    prepared = source
    cut_report = None
    if use_auto_cut:
        emit(18, "正在检测静音并自动剪辑")
        prepared, cut_report = auto_cut(source, out_dir, threshold_db, min_silence)
    emit(36, "正在生成 AI 配音")
    voice_path = synthesize_voice(script, voice, out_dir, log)
    voice_duration = duration_of(voice_path)
    if editing_style not in EDIT_STYLES:
        raise PipelineError(f"未知剪辑模板：{editing_style}")
    lines = split_script(script, max_chars=EDIT_STYLES[editing_style]["max_chars"])
    timeline = timeline_for(lines, voice_duration)
    write_srt(timeline, out_dir / "captions.srt")
    emit(54, "正在生成字幕和标题层")
    overlays = []
    title_path = out_dir / "overlay-title.png"
    title_overlay(title, title_path)
    overlays.append((title_path, None))
    for item in timeline:
        caption_path = out_dir / f"caption-{item['index']:02d}.png"
        caption_overlay(item["text"], caption_path, editing_style)
        overlays.append((caption_path, (item["start"], item["end"])))

    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-stream_loop", "-1", "-i", str(prepared)]
    for path, _ in overlays:
        command += ["-loop", "1", "-i", str(path)]
    audio_index = 1 + len(overlays)
    command += ["-i", str(voice_path)]

    filters = [f"[0:v]{motion_filter(motion_preset)}[base]"]
    previous = "base"
    for index, (_, timing) in enumerate(overlays, 1):
        output_label = f"layer{index}"
        if timing:
            caption_label = f"caption{index}"
            animation, x, y = caption_animation_filter(index, editing_style, timing[0], caption_label)
            filters.append(animation)
            filters.append(
                f"[{previous}][{caption_label}]overlay=x='{x}':y='{y}':"
                f"enable='between(t,{timing[0]:.3f},{timing[1]:.3f})'[{output_label}]"
            )
        else:
            filters.append(f"[{previous}][{index}:v]overlay=0:0[{output_label}]")
        previous = output_label

    final = out_dir / "final.mp4"
    emit(68, "正在合成竖屏视频")
    command += [
        "-filter_complex", ";".join(filters), "-map", f"[{previous}]", "-map", f"{audio_index}:a:0",
        "-t", f"{voice_duration:.3f}", "-r", "30", "-c:v", "libx264", "-preset", "veryfast",
        "-af", AUDIO_NORMALIZATION, "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(final)
    ]
    run(command, log)
    emit(88, "正在全片解码验证")
    run(["ffmpeg", "-hide_banner", "-v", "error", "-i", str(final), "-f", "null", "-"], log)
    cover = out_dir / "cover.jpg"
    contact = out_dir / "contact-sheet.jpg"
    make_cover(prepared, title, cover)
    make_contact_sheet(final, contact)
    emit(96, "正在整理封面和交付文件")
    result = {
        "final": str(final),
        "cover": str(cover),
        "captions": str(out_dir / "captions.srt"),
        "contact_sheet": str(contact),
        "duration": duration_of(final),
        "voice": voice,
        "motion_preset": motion_preset,
        "motion": MOTION_PRESETS[motion_preset],
        "editing_style": editing_style,
        "editing": EDIT_STYLES[editing_style],
        "auto_cut": cut_report,
        "source": str(source),
        "prepared_source": str(prepared)
    }
    (out_dir / "project.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def transcribe_source(source: Path, out_dir: Path) -> dict:
    whisper = shutil.which("whisper")
    if not whisper:
        raise PipelineError("未找到 Whisper")
    audio = out_dir / "source-audio.wav"
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source), "-vn", "-ar", "16000", "-ac", "1", str(audio)])
    run([whisper, str(audio), "--model", "tiny", "--language", "Chinese", "--output_dir", str(out_dir), "--output_format", "all", "--word_timestamps", "True"])
    data = json.loads((out_dir / "source-audio.json").read_text(encoding="utf-8"))
    return {"text": data.get("text", "").strip(), "segments": data.get("segments", [])}
