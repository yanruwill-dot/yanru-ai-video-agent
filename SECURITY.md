# Security

## 公网部署

- 必须设置长随机 `VIDEO_AGENT_API_KEY`。
- 只允许明确的 `VIDEO_AGENT_ALLOWED_ORIGINS`。
- 使用 HTTPS 反向代理；不要把无密钥的 8788 端口直接暴露到公网。
- 把 `runs/`、`uploads/`、`voice-uploads/`、`voices/` 与 `.env` 视为私密数据。

## 声音授权

只处理本人或已获明确授权的声音。仓库维护者不会接收用户声音样本，也不会为绕过授权提供支持。

## 报告漏洞

请通过 GitHub Security Advisory 私下报告可复现的安全问题，不要在公开 Issue 中附带密钥、Cookie、声音、视频或知识库正文。
