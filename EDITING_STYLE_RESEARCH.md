# GitHub 公开剪辑手法研究

版本：1.3.0
日期：2026-07-27

本研究只提炼公开代码中的剪辑机制，不复制剪映、开拍等商业软件的私有模板、商标素材或受保护资源。“剪映感”“开拍感”是面向用户理解的风格描述，不代表官方模板。

| 公开项目 | 代码证据 | 提炼出的机制 | 工作台落地 |
|---|---|---|---|
| Remotion TikTok Template | [`Page.tsx`](https://github.com/remotion-dev/template-tiktok/blob/cbe0d33875349c7d043a0edf0c123f098ce18c28/src/CaptionedVideo/Page.tsx)、[`SubtitlePage.tsx`](https://github.com/remotion-dev/template-tiktok/blob/cbe0d33875349c7d043a0edf0c123f098ce18c28/src/CaptionedVideo/SubtitlePage.tsx) | 120px 级大字、黑色粗描边、当前词绿色高亮、5 帧弹入 | 大字弹跳、重点色、快速缩放入场 |
| Short Video Maker | [`PortraitVideo.tsx`](https://github.com/gyoridavid/short-video-maker/blob/9bb9a212ced86caa7e09099c382da1a44d638760/src/components/videos/PortraitVideo.tsx)、[`utils.ts`](https://github.com/gyoridavid/short-video-maker/blob/9bb9a212ced86caa7e09099c382da1a44d638760/src/components/utils.ts) | 单行短字幕、当前词色块、描边与阴影、按时间间隔分页 | 开拍感短句色块、知识口播关键词高亮 |
| Auto-Editor | [`editmethods.nim`](https://github.com/WyattBlue/auto-editor/blob/2b30d6097fd4e86061bae0bc5c08d8dd74090c55/src/editmethods.nim)、[`SKILL.md`](https://github.com/WyattBlue/auto-editor/blob/2b30d6097fd4e86061bae0bc5c08d8dd74090c55/skills/auto-editor/SKILL.md) | 音量、画面运动、字幕词语的分层判断；静音留边；高运动片段变焦 | 静音剪辑保留呼吸边缘、镜头动效与字幕模板独立组合 |
| MoneyPrinterTurbo | [`subtitle.py`](https://github.com/harry0703/MoneyPrinterTurbo/blob/95dd03ed0255ed8a8bcefc118ab869addfaa27cc/app/services/subtitle.py) | Whisper 词级时间戳、VAD、500ms 静音分段、标点拆句 | 短句分页、字幕节奏与口播时间轴对齐 |

## 工作台新增模板

1. `经典口播`：原有稳重底栏字幕。
2. `剪映感·大字弹跳`：108px 大字、10px 黑描边、重点黄字、快速弹入。
3. `开拍感·口播重点`：单屏短句、重点青色、半透明色块、轻推入场。
4. `卡点快切·冲击字幕`：132px 中央大字、重点粉色、冲击缩放。
5. `知识口播·关键词高亮`：高信息密度下三分之一字幕、业务词青色强调。
6. `剪映经典·清透标题`：玻璃字幕卡、蓝色重点词、稳定轻推镜头。
7. `开拍·老板观点`：观点型大字、暖色强调、稳定人物聚焦。
8. `开拍·故事叙述`：电影感双行字幕、柔和暖白字、呼吸推镜。

每套模板会自动匹配适合的轻推、呼吸或节奏运动，最终进入 FFmpeg 成片，而不是只做前端预览。
