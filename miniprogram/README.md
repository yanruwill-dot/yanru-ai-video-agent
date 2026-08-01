# 微信小程序版

这是“AI 视频智能体”的原生小程序界面，不使用 `web-view` 套壳。它复用同一个 Python/FFmpeg HTTPS 生成引擎，支持：

- 从相册或相机选择视频并上传。
- 得到大脑与 Obsidian 检索、AI 拆解与 Whisper 转写。
- 剪映经典、开拍口播等八套剪辑模板。
- 选择已有音色，或上传本人声音与逐字稿后建立 Fish Speech 本地声音档案。
- 提交真实生成任务并轮询进度。
- 预览封面、成片，保存视频到手机相册。

## 微信开发者工具

1. 导入当前 `miniprogram/` 目录。
2. 开发阶段可使用 `touristappid`；正式发布前把 `project.config.json` 的 `appid` 换成自己的小程序 AppID。
3. 在工作台右上角填写 HTTPS 生成引擎地址和访问密钥。

## 正式发布前必须配置

在微信公众平台的小程序后台，把生成引擎域名加入：

- request 合法域名
- downloadFile 合法域名
- uploadFile 合法域名

正式版必须使用有效 HTTPS 证书，不能填写 `127.0.0.1`、局域网 IP 或 Cloudflare 临时域名。`project.config.json` 中的 `urlCheck: false` 只方便开发者工具本地联调，不会绕过真机和审核要求。

## 上传边界

小程序使用官方 `wx.uploadFile` 把素材流式上传到后端 multipart 接口，不会先把整个视频读进小程序内存。为了控制移动网络耗时，界面限制单个视频不超过 200 MB，声音样本不超过 20 MB。更大的生产素材建议在桌面工作台上传。
