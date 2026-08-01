# 第三方组件说明

本仓库只发布颜汝 AI 视频智能体的原创代码。运行时会调用下列独立项目；它们不随本仓库重新授权，也不打包个人声音、模型权重或商业素材。

| 组件 | 用途 | 上游与许可证 |
| --- | --- | --- |
| Fish Speech | 本地参考音色与连续配音 | [fishaudio/fish-speech](https://github.com/fishaudio/fish-speech)；许可证随版本变化。当前上游采用 Fish Audio Research License，商业使用需另行获得书面许可。经本项目实测的 1.5 代码提交 `58046ea` 为 Apache-2.0，1.5 模型卡标注 CC BY-NC-SA 4.0，仅限非商业用途 |
| FFmpeg | 探测、剪辑、混音和编码 | [ffmpeg.org](https://ffmpeg.org/)，LGPL/GPL 取决于本地构建选项 |
| edge-tts | 未配置 Fish Speech 时的基础公共音色 | [rany2/edge-tts](https://github.com/rany2/edge-tts)，LGPL-3.0 |
| Pillow | 封面与字幕画面处理 | [python-pillow/Pillow](https://github.com/python-pillow/Pillow)，HPND |

声音样本、笔记、视频素材、字体、音乐和模型权重的使用权由部署者自行确认。Fish Speech 的代码许可不等于模型许可，最新版本也不沿用旧版本许可。请勿克隆未获授权的声音，也不要把私人知识库或密钥提交到公开仓库。
