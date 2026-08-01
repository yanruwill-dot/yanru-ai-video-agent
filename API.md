# HTTP API

设置 `VIDEO_AGENT_API_KEY` 后，所有 `/api/`、`/runs/` 和 `/voices/` 请求都需要 `X-Video-Agent-Key` 请求头。媒体元素也支持 `?key=` 查询参数。

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/api/health` | 引擎、Fish Speech 和知识连接状态 |
| GET | `/api/latest` | 最近一次完成的生成任务 |
| GET | `/api/voices` | 本地 Fish 声音档案 |
| POST | `/api/knowledge/search` | 得到大脑与 Obsidian 只读检索 |
| POST | `/api/upload?name=video.mp4` | 浏览器原始视频流上传 |
| POST | `/api/upload-file?name=video.mp4` | 小程序 multipart 视频上传 |
| POST | `/api/upload-audio?name=sample.wav` | 浏览器声音样本上传与校验 |
| POST | `/api/upload-audio-file?name=sample.wav` | 小程序 multipart 声音上传 |
| POST | `/api/clone` | 建立 Fish Speech 本地声音档案 |
| POST | `/api/analyze` | Whisper 转写与媒体分析 |
| POST | `/api/autocut` | 静音检测和自动剪辑 |
| POST | `/api/generate` | 配音、字幕、封面和 MP4 完整生成 |
| GET | `/api/jobs/<id>` | 查询任务状态 |
| GET | `/runs/<id>/<file>` | 下载任务产物 |

## 知识检索

```json
{
  "query": "视频智能体 自动剪辑",
  "include_getnote": true,
  "include_obsidian": true,
  "limit": 5
}
```

返回结果含 `source`、`title`、`content`；Obsidian 结果含本地 `path`，得到大脑结果含真实 `note_id`。连接失败会进入 `errors`，不会伪造成空成功。

## 建立 Fish 声音档案

```json
{
  "sample_path": "/local/upload/sample.wav",
  "name": "我的专属音色",
  "reference_text": "这是声音样本里准确说出的完整文字。",
  "consent": true
}
```

`consent=false`、逐字稿过短、音频低于 10 秒或高于 5 分钟都会被拒绝。

## 生成成片

```json
{
  "source_path": "/local/upload/source.mp4",
  "title": "我把内容大脑接进了视频智能体",
  "script": "完整口播文案",
  "voice": "fish:your_voice_id",
  "editing_style": "jianying_big",
  "motion_preset": "beat_impact",
  "auto_cut": true,
  "threshold_db": -35,
  "min_silence": 0.65
}
```

公共音色可使用 `zh-CN-YunxiNeural` 等 Edge TTS voice ID。

剪辑模板：`classic`、`jianying_big`、`jianying_clean`、`keyword_punch`、`kaipai_talk`、`kaipai_boss`、`kaipai_story`、`knowledge_highlight`。

镜头动效：`none`、`smart_push`、`breath_focus`、`beat_impact`。
