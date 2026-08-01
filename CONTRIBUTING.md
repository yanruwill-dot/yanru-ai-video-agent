# Contributing

欢迎提交小而可验证的改进。

1. Fork 仓库并创建功能分支。
2. 不要提交声音样本、视频素材、模型权重、笔记正文、账号信息或运行目录。
3. 为行为变化补测试。
4. 运行：

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile app.py pipeline.py voice_clone.py knowledge.py runtime_config.py
node --check static/app.js
```

Pull Request 请说明改了什么、为什么改、测试结果和仍然存在的边界。
