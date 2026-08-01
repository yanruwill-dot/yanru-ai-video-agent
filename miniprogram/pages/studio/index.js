const api = require("../../utils/api");

const MOTION_BY_STYLE = {
  classic: "none",
  jianying_big: "beat_impact",
  jianying_clean: "smart_push",
  keyword_punch: "beat_impact",
  kaipai_talk: "smart_push",
  kaipai_boss: "smart_push",
  kaipai_story: "breath_focus",
  knowledge_highlight: "none"
};

const DEFAULT_SCRIPT = "我把内容大脑接进了视频智能体。素材上传后，系统先检索得到大脑和 Obsidian，再把可追溯的依据放进脚本。确认内容后，Fish Speech 生成授权声音，FFmpeg 自动完成字幕、动效、封面和竖屏成片。";

Page({
  data: {
    connected: false,
    connectionLabel: "生成引擎未连接",
    connectionDetail: "请连接 HTTPS 云端引擎",
    showConnection: false,
    connecting: false,
    connectionError: "",
    apiInput: "",
    keyInput: "",
    sourceLabel: "选择视频素材",
    sourceMeta: "MP4 / MOV · 建议不超过 200 MB",
    sourcePreview: "",
    sourcePath: "",
    transcript: "",
    title: "我把内容大脑接进了视频智能体",
    script: DEFAULT_SCRIPT,
    charCount: DEFAULT_SCRIPT.replace(/\s/g, "").length,
    knowledgeQuery: "视频智能体 自动剪辑",
    knowledgeResult: "",
    autoCut: true,
    threshold: -35,
    silence: 0.65,
    templates: [
      { value: "classic", kind: "基础", name: "清晰口播", desc: "克制底栏 · 正式讲解" },
      { value: "jianying_big", kind: "剪映经典", name: "大字弹跳", desc: "重点黄字 · 弹性入场" },
      { value: "jianying_clean", kind: "剪映经典", name: "清透标题", desc: "玻璃字幕 · 轻推镜头" },
      { value: "keyword_punch", kind: "剪映经典", name: "卡点快切", desc: "冲击字幕 · 节奏变焦" },
      { value: "kaipai_talk", kind: "开拍口播", name: "口播重点", desc: "短句色块 · 智能轻推" },
      { value: "kaipai_boss", kind: "开拍口播", name: "老板观点", desc: "观点大字 · 稳定聚焦" },
      { value: "kaipai_story", kind: "开拍口播", name: "故事叙述", desc: "电影字幕 · 呼吸推镜" },
      { value: "knowledge_highlight", kind: "知识表达", name: "关键词高亮", desc: "高信息密度 · 自动强调" }
    ],
    editingStyle: "jianying_big",
    voices: [
      { id: "zh-CN-YunxiNeural", name: "云希 · 沉稳男声" },
      { id: "zh-CN-XiaoxiaoNeural", name: "晓晓 · 自然女声" },
      { id: "zh-CN-YunjianNeural", name: "云健 · 专业男声" }
    ],
    voiceNames: ["云希 · 沉稳男声", "晓晓 · 自然女声", "云健 · 专业男声"],
    voiceIndex: 0,
    voiceSamplePath: "",
    voiceSampleLabel: "上传本人声音样本",
    voiceName: "我的专属音色",
    voiceReferenceText: "",
    voiceConsent: false,
    busy: false,
    busyAction: "",
    progress: 0,
    jobMessage: "等待任务",
    resultVideo: "",
    coverUrl: "",
    srtUrl: ""
  },

  onLoad() {
    const connection = api.getConnection();
    this.setData({
      apiInput: connection.base,
      keyInput: connection.key,
      showConnection: !connection.base
    });
    if (connection.base) this.connect();
  },

  inputField(event) {
    const field = event.currentTarget.dataset.field;
    const value = event.detail.value;
    const next = { [field]: value };
    if (field === "script") next.charCount = value.replace(/\s/g, "").length;
    this.setData(next);
  },

  openConnection() {
    const connection = api.getConnection();
    this.setData({ showConnection: true, apiInput: connection.base, keyInput: connection.key, connectionError: "" });
  },

  closeConnection() {
    if (this.data.connected) this.setData({ showConnection: false });
  },

  async saveConnection() {
    this.setData({ connecting: true, connectionError: "" });
    try {
      api.saveConnection(this.data.apiInput, this.data.keyInput);
      const connected = await this.connect();
      if (connected) this.setData({ showConnection: false });
    } catch (error) {
      this.setData({ connectionError: error.message });
    } finally {
      this.setData({ connecting: false });
    }
  },

  async connect() {
    try {
      const health = await api.request("/api/health");
      const connection = api.getConnection();
      this.setData({
        connected: true,
        connectionLabel: "生成引擎已连接",
        connectionDetail: `${health.version || "1.6"} · ${connection.base}`,
        connectionError: ""
      });
      await this.loadVoices();
      await this.loadLatest();
      return true;
    } catch (error) {
      this.setData({
        connected: false,
        connectionLabel: "生成引擎未连接",
        connectionDetail: error.message,
        connectionError: error.message
      });
      return false;
    }
  },

  async loadVoices(selectId = "") {
    const result = await api.request("/api/voices");
    const builtins = [
      { id: "zh-CN-YunxiNeural", name: "云希 · 沉稳男声" },
      { id: "zh-CN-XiaoxiaoNeural", name: "晓晓 · 自然女声" },
      { id: "zh-CN-YunjianNeural", name: "云健 · 专业男声" }
    ];
    const voices = [...(result.voices || []), ...builtins]
      .filter((item, index, rows) => rows.findIndex(row => row.id === item.id) === index);
    const target = selectId || voices[0]?.id;
    const voiceIndex = Math.max(0, voices.findIndex(item => item.id === target));
    this.setData({ voices, voiceNames: voices.map(item => item.name), voiceIndex });
  },

  async loadLatest() {
    try {
      const job = await api.request("/api/latest");
      this.showResult(job);
    } catch (_) {}
  },

  chooseVideo() {
    if (!this.data.connected) {
      this.openConnection();
      return;
    }
    wx.chooseMedia({
      count: 1,
      mediaType: ["video"],
      sourceType: ["album", "camera"],
      maxDuration: 300,
      success: async result => {
        const file = result.tempFiles[0];
        if (file.size > 200 * 1024 * 1024) {
          wx.showToast({ title: "视频请控制在 200 MB 内", icon: "none" });
          return;
        }
        this.setData({
          sourcePreview: file.tempFilePath,
          sourceLabel: "正在上传视频",
          sourceMeta: `${(file.size / 1024 / 1024).toFixed(1)} MB`
        });
        try {
          const suffix = file.tempFilePath.match(/\.[A-Za-z0-9]+$/)?.[0] || ".mp4";
          const uploaded = await api.uploadFile(file.tempFilePath, "/api/upload-file", `miniapp-${Date.now()}${suffix}`);
          this.setData({
            sourcePath: uploaded.path,
            sourceLabel: "视频素材已载入",
            sourceMeta: `${(uploaded.bytes / 1024 / 1024).toFixed(1)} MB · 可开始拆解`
          });
        } catch (error) {
          this.setData({ sourceLabel: "上传失败", sourceMeta: error.message });
        }
      }
    });
  },

  selectTemplate(event) {
    this.setData({ editingStyle: event.currentTarget.dataset.value });
  },

  changeVoice(event) {
    this.setData({ voiceIndex: Number(event.detail.value) });
  },

  toggleAutoCut(event) {
    this.setData({ autoCut: event.detail.value });
  },

  toggleConsent() {
    this.setData({ voiceConsent: !this.data.voiceConsent });
  },

  chooseVoiceSample() {
    if (!this.data.connected) {
      this.openConnection();
      return;
    }
    wx.chooseMessageFile({
      count: 1,
      type: "file",
      extension: ["mp3", "m4a", "wav"],
      success: async result => {
        const file = result.tempFiles[0];
        if (file.size > 20 * 1024 * 1024) {
          wx.showToast({ title: "声音样本不能超过 20 MB", icon: "none" });
          return;
        }
        this.setData({ voiceSampleLabel: "正在检查声音样本" });
        try {
          const uploaded = await api.uploadFile(file.path, "/api/upload-audio-file", file.name || `voice-${Date.now()}.m4a`);
          this.setData({
            voiceSamplePath: uploaded.path,
            voiceSampleLabel: `可克隆 · ${Number(uploaded.duration).toFixed(1)} 秒`
          });
        } catch (error) {
          this.setData({ voiceSamplePath: "", voiceSampleLabel: error.message });
        }
      }
    });
  },

  payload() {
    const voice = this.data.voices[this.data.voiceIndex]?.id || "zh-CN-YunxiNeural";
    return {
      source_path: this.data.sourcePath,
      title: this.data.title.trim(),
      script: this.data.script.trim(),
      voice,
      motion_preset: MOTION_BY_STYLE[this.data.editingStyle] || "smart_push",
      editing_style: this.data.editingStyle,
      auto_cut: this.data.autoCut,
      threshold_db: Number(this.data.threshold),
      min_silence: Number(this.data.silence)
    };
  },

  async submit(kind, payload) {
    const created = await api.request(`/api/${kind}`, { method: "POST", data: payload });
    return this.poll(created.job.id);
  },

  async poll(jobId) {
    for (;;) {
      const job = await api.request(`/api/jobs/${encodeURIComponent(jobId)}`);
      this.setData({ progress: Number(job.progress || 0), jobMessage: job.message || "处理中" });
      if (job.status === "completed") return job;
      if (job.status === "failed") throw new Error(job.message || "任务失败");
      await new Promise(resolve => setTimeout(resolve, 1200));
    }
  },

  async analyze() {
    await this.runAction("analyze", async () => {
      const job = await this.submit("analyze", { source_path: this.data.sourcePath });
      const transcript = job.result?.transcript?.text || "";
      this.setData({ transcript, progress: 100, jobMessage: `转写完成 · ${transcript.length} 字` });
    });
  },

  useTranscript() {
    const script = this.data.transcript;
    this.setData({ script, charCount: script.replace(/\s/g, "").length });
  },

  async searchKnowledge() {
    const query = this.data.knowledgeQuery.trim();
    if (!query) {
      wx.showToast({ title: "请先输入检索关键词", icon: "none" });
      return;
    }
    await this.runAction("knowledge", async () => {
      const result = await api.request("/api/knowledge/search", {
        method: "POST",
        data: { query, include_getnote: true, include_obsidian: true, limit: 4 }
      });
      const lines = (result.results || []).map(item => `【${item.source === "getnote" ? "得到大脑" : "Obsidian"}】${item.title}\n${item.content}`);
      const errors = (result.errors || []).map(item => `${item.source}：${item.error}`);
      this.setData({ knowledgeResult: [...lines, ...errors].join("\n\n") || "没有找到相关内容" });
      this.setData({ progress: 100, jobMessage: `找到 ${(result.results || []).length} 条依据` });
    });
  },

  async cloneVoice() {
    if (!this.data.voiceConsent) {
      wx.showToast({ title: "请先确认声音授权", icon: "none" });
      return;
    }
    if (this.data.voiceReferenceText.trim().length < 8) {
      wx.showToast({ title: "请填写样本逐字稿", icon: "none" });
      return;
    }
    await this.runAction("clone", async () => {
      const job = await this.submit("clone", {
        sample_path: this.data.voiceSamplePath,
        name: this.data.voiceName.trim() || "我的克隆音色",
        reference_text: this.data.voiceReferenceText.trim(),
        consent: true
      });
      await this.loadVoices(job.result?.id || job.result?.voice_id);
      wx.showToast({ title: "声音克隆完成", icon: "success" });
    });
  },

  async generate() {
    if (!this.data.sourcePath || !this.data.title.trim() || !this.data.script.trim()) {
      wx.showToast({ title: "请先补齐素材、标题和文案", icon: "none" });
      return;
    }
    await this.runAction("generate", async () => {
      const job = await this.submit("generate", this.payload());
      this.showResult(job);
      wx.pageScrollTo({ selector: "#result", duration: 320 });
    });
  },

  async runAction(name, action) {
    if (this.data.busy) return;
    this.setData({ busy: true, busyAction: name, progress: 2, jobMessage: "正在创建任务" });
    try {
      await action();
    } catch (error) {
      this.setData({ progress: 0, jobMessage: error.message });
      wx.showToast({ title: error.message, icon: "none", duration: 2600 });
    } finally {
      this.setData({ busy: false, busyAction: "" });
    }
  },

  showResult(job) {
    if (!job?.id) return;
    this.setData({
      progress: 100,
      jobMessage: "生成完成",
      resultVideo: api.assetUrl(job.id, "final.mp4"),
      coverUrl: api.assetUrl(job.id, "cover.jpg"),
      srtUrl: api.assetUrl(job.id, "captions.srt")
    });
  },

  saveVideo() {
    wx.showLoading({ title: "正在下载成片" });
    wx.downloadFile({
      url: this.data.resultVideo,
      success: result => {
        if (result.statusCode !== 200) throw new Error("视频下载失败");
        wx.saveVideoToPhotosAlbum({
          filePath: result.tempFilePath,
          success: () => wx.showToast({ title: "已保存到相册", icon: "success" }),
          fail: error => wx.showToast({ title: error.errMsg || "保存失败", icon: "none" })
        });
      },
      fail: error => wx.showToast({ title: error.errMsg || "下载失败", icon: "none" }),
      complete: () => wx.hideLoading()
    });
  },

  copySrtLink() {
    wx.setClipboardData({ data: this.data.srtUrl });
  }
});
