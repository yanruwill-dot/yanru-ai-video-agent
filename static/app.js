const $ = (selector) => document.querySelector(selector);
const connection = new URLSearchParams(location.hash.replace(/^#/, ""));
const LOCAL_ENGINE_ORIGIN = "http://127.0.0.1:8788";
const savedOrigin = localStorage.getItem("video-agent-api") || "";
const savedKey = localStorage.getItem("video-agent-key") || "";
let requestedOrigin = connection.get("api") || savedOrigin;
let API_ORIGIN = resolveOrigin(requestedOrigin);
let API_KEY = connection.get("key") || savedKey;

function resolveOrigin(origin) {
  const value = String(origin || "").trim().replace(/\/$/, "");
  if (isAllowedConnectionOrigin(value)) return value;
  return location.hostname.endsWith("github.io") ? LOCAL_ENGINE_ORIGIN : "";
}

function isAllowedConnectionOrigin(value) {
  return /^https:\/\/[A-Za-z0-9.-]+(?::\d+)?$/.test(value)
    || /^http:\/\/(127\.0\.0\.1|localhost)(?::\d+)?$/.test(value);
}

const apiUrl = (path) => `${API_ORIGIN}${path}`;
const apiFetch = (path, options = {}) => {
  const headers = new Headers(options.headers || {});
  if (API_KEY) headers.set("X-Video-Agent-Key", API_KEY);
  return fetch(apiUrl(path), { ...options, headers });
};
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
const state = {
  transcript: "",
  currentJob: null,
  localPreview: null,
  voiceSamplePath: "",
  knowledgeResults: [],
  lastMessage: ""
};

const sourcePath = $("#sourcePath");
const log = $("#log");
const progressBar = $("#progressBar");
const progressText = $("#progressText");
const jobState = $("#jobState");

function note(message) {
  const time = new Date().toLocaleTimeString("zh-CN", { hour12: false });
  log.textContent += `\n[${time}] ${message}`;
  log.scrollTop = log.scrollHeight;
}

function setProgress(value, message) {
  const safe = Math.max(0, Math.min(100, Number(value || 0)));
  progressBar.style.width = `${safe}%`;
  progressText.textContent = `${safe}%`;
  jobState.textContent = message || "处理中";
  $("#mobileProgress").textContent = safe ? `${safe}% · ${message || "处理中"}` : message || "等待任务";
}

function runUrl(jobId, name) {
  const path = `/runs/${encodeURIComponent(jobId)}/${encodeURIComponent(name)}`;
  const query = API_KEY ? `?key=${encodeURIComponent(API_KEY)}` : "";
  return apiUrl(`${path}${query}`);
}

function showResult(job) {
  const videoUrl = runUrl(job.id, "final.mp4");
  const coverUrl = runUrl(job.id, "cover.jpg");
  const srtUrl = runUrl(job.id, "captions.srt");
  const video = $("#finalPreview");
  video.src = videoUrl;
  video.classList.add("ready");
  $("#coverPreview").src = coverUrl;
  $("#coverPreview").classList.add("ready");
  $("#coverEmpty").style.display = "none";
  $("#downloadVideo").href = videoUrl;
  $("#downloadVideo").classList.remove("disabled");
  $("#downloadSrt").href = srtUrl;
  $("#downloadSrt").classList.remove("disabled");
  const duration = Number(job.result?.duration || 0);
  $("#facts").innerHTML = `<span><b>${duration.toFixed(1)}s</b>时长</span><span><b>1080×1920</b>画幅</span><span><b>${job.id}</b>任务</span>`;
}

async function health() {
  try {
    const response = await apiFetch("/api/health");
    const data = await response.json();
    if (!data.ok) throw new Error("服务未就绪");
    $("#health").classList.add("ok");
    $("#health").classList.remove("error");
    $("#health").innerHTML = requestedOrigin
      ? "<i></i>HTTPS 视频与声音引擎已就绪"
      : "<i></i>长期生成引擎已连接";
    const clone = data.voice_clone || {};
    $("#cloneEngine").textContent = clone.clone_enabled ? "Fish Speech 已连接" : "Fish Speech 未配置";
    const knowledge = data.knowledge || {};
    const knowledgeNames = [knowledge.getnote_configured && "得到大脑", knowledge.obsidian_configured && "Obsidian"].filter(Boolean);
    $("#knowledgeState").textContent = knowledgeNames.length ? `${knowledgeNames.join(" + ")} 已连接` : "等待配置内容源";
    $("#connectionState").textContent = `连接成功 · ${API_ORIGIN || "当前站点"}`;
    $("#connectionState").classList.remove("error");
    return true;
  } catch {
    $("#health").classList.remove("ok");
    $("#health").classList.add("error");
    $("#health").innerHTML = "<i></i>长期生成引擎正在恢复 · 请稍后重试";
    $("#connectionState").textContent = "未连接。手机使用时请填写可访问的 HTTPS 引擎地址。";
    $("#connectionState").classList.add("error");
    return false;
  }
}

async function loadVoices(selectId = "") {
  const response = await apiFetch("/api/voices");
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "声音库读取失败");
  const select = $("#voice");
  const builtins = [
    ["zh-CN-YunxiNeural", "云希 · 沉稳男声"],
    ["zh-CN-XiaoxiaoNeural", "晓晓 · 自然女声"],
    ["zh-CN-YunjianNeural", "云健 · 专业男声"]
  ];
  const options = [
    ...data.voices.map(item => [item.id, item.name]),
    ...builtins
  ].map(([value, label]) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    return option;
  });
  select.replaceChildren(...options);
  const target = selectId || data.voices[0]?.id || builtins[0][0];
  select.value = target;
}

async function loadLatest() {
  try {
    const response = await apiFetch("/api/latest");
    if (!response.ok) return;
    const job = await response.json();
    if (!job.id) return;
    showResult(job);
    note(`已载入最近成片：${job.id}`);
  } catch {}
}

async function upload(file) {
  $("#uploadState").textContent = `上传中 0% · ${file.name}`;
  const response = await apiFetch(`/api/upload?name=${encodeURIComponent(file.name)}`, {
    method: "POST",
    headers: { "Content-Type": "application/octet-stream" },
    body: file
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "上传失败");
  sourcePath.value = data.path;
  if (state.localPreview) URL.revokeObjectURL(state.localPreview);
  state.localPreview = URL.createObjectURL(file);
  const preview = $("#sourcePreview");
  preview.src = state.localPreview;
  preview.classList.add("ready");
  $("#uploadState").textContent = `已载入 · ${(data.bytes / 1024 / 1024).toFixed(1)} MB`;
  note(`素材已载入：${file.name}`);
}

async function uploadVoice(file) {
  $("#voiceUploadState").textContent = `正在检查 · ${file.name}`;
  const response = await apiFetch(`/api/upload-audio?name=${encodeURIComponent(file.name)}`, {
    method: "POST",
    headers: { "Content-Type": "application/octet-stream" },
    body: file
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "声音样本上传失败");
  state.voiceSamplePath = data.path;
  $("#voiceUploadState").textContent = `可克隆 · ${Number(data.duration).toFixed(1)} 秒 · ${(data.bytes / 1024 / 1024).toFixed(1)} MB`;
  $("#cloneBtn").disabled = false;
  note(`声音样本已通过检查：${Number(data.duration).toFixed(1)} 秒`);
}

async function submit(kind, payload) {
  setProgress(2, "正在创建任务");
  note(`提交 ${kind} 任务`);
  const response = await apiFetch(`/api/${kind}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "任务提交失败");
  state.currentJob = data.job.id;
  return poll(data.job.id);
}

async function poll(jobId) {
  for (;;) {
    const response = await apiFetch(`/api/jobs/${encodeURIComponent(jobId)}`);
    const job = await response.json();
    setProgress(job.progress, job.message);
    if (job.message && job.message !== state.lastMessage) {
      note(job.message);
      state.lastMessage = job.message;
    }
    if (job.status === "completed") return job;
    if (job.status === "failed") throw new Error(job.message || "任务失败");
    await new Promise(resolve => setTimeout(resolve, 1200));
  }
}

function payload() {
  const editingStyle = document.querySelector('input[name="editStyle"]:checked')?.value || "jianying_big";
  return {
    source_path: sourcePath.value.trim(),
    title: $("#title").value.trim(),
    script: $("#script").value.trim(),
    voice: $("#voice").value,
    motion_preset: MOTION_BY_STYLE[editingStyle] || "smart_push",
    editing_style: editingStyle,
    auto_cut: $("#autoCut").checked,
    threshold_db: Number($("#threshold").value),
    min_silence: Number($("#silence").value)
  };
}

$("#videoFile").addEventListener("change", async (event) => {
  const [file] = event.target.files;
  if (!file) return;
  try { await upload(file); } catch (error) { note(`错误：${error.message}`); }
});

$("#voiceFile").addEventListener("change", async (event) => {
  const [file] = event.target.files;
  if (!file) return;
  try {
    await uploadVoice(file);
  } catch (error) {
    state.voiceSamplePath = "";
    $("#cloneBtn").disabled = true;
    $("#voiceUploadState").textContent = error.message;
    note(`错误：${error.message}`);
  }
});

$("#cloneBtn").addEventListener("click", async () => {
  if (!state.voiceSamplePath) {
    note("请先上传声音样本");
    return;
  }
  if (!$("#voiceConsent").checked) {
    note("请先确认声音授权");
    return;
  }
  const button = $("#cloneBtn");
  button.disabled = true;
  try {
    const referenceText = $("#voiceReferenceText").value.trim();
    if (referenceText.length < 8) throw new Error("请填写声音样本对应的逐字稿，至少 8 个字");
    const job = await submit("clone", {
      sample_path: state.voiceSamplePath,
      name: $("#voiceName").value.trim() || "我的克隆音色",
      reference_text: referenceText,
      consent: true
    });
    await loadVoices(job.result.id);
    const preview = $("#voicePreview");
    const voiceId = job.result.voice_id;
    const voiceQuery = API_KEY ? `?key=${encodeURIComponent(API_KEY)}` : "";
    preview.src = apiUrl(`/voices/${encodeURIComponent(voiceId)}/preview.mp3${voiceQuery}`);
    preview.classList.add("ready");
    note(`Fish Speech 声音档案已建立：${job.result.name}`);
  } catch (error) {
    setProgress(0, "克隆失败");
    note(`错误：${error.message}`);
  } finally {
    button.disabled = false;
  }
});

function bindCardGroup(name, prefix) {
  document.querySelectorAll(`input[name="${name}"]`).forEach(input => {
    input.addEventListener("change", () => {
      const grid = input.closest(".template-library");
      grid.querySelectorAll(".template-card").forEach(card => card.classList.remove("active"));
      input.closest(".template-card").classList.add("active");
      note(`${prefix}：${input.closest(".template-card").querySelector("b").textContent}`);
    });
  });
}

bindCardGroup("editStyle", "已选择剪辑模板");

$("#analyzeBtn").addEventListener("click", async () => {
  try {
    const job = await submit("analyze", { source_path: sourcePath.value.trim() });
    state.transcript = job.result.transcript.text || "";
    note(`AI 转写完成：${state.transcript.length} 字`);
    setProgress(100, "拆解完成");
  } catch (error) {
    setProgress(0, "任务失败"); note(`错误：${error.message}`);
  }
});

$("#cutBtn").addEventListener("click", async () => {
  try {
    const job = await submit("autocut", payload());
    const video = $("#cutPreview");
    video.src = runUrl(job.id, "auto-cut.mp4");
    video.classList.add("ready");
    const saved = job.result.report.source_duration - job.result.report.output_duration;
    note(`自动剪辑完成，删除静音 ${Math.max(0, saved).toFixed(2)} 秒`);
  } catch (error) {
    setProgress(0, "任务失败"); note(`错误：${error.message}`);
  }
});

$("#generateBtn").addEventListener("click", async () => {
  const button = $("#generateBtn");
  button.disabled = true;
  try {
    const job = await submit("generate", payload());
    showResult(job);
    note(`真实 MP4 已生成：runs/${job.id}/final.mp4`);
  } catch (error) {
    setProgress(0, "任务失败"); note(`错误：${error.message}`);
  } finally {
    button.disabled = false;
  }
});

$("#mobileGenerateBtn").addEventListener("click", () => {
  $("#launchStep").scrollIntoView({ behavior: "smooth", block: "start" });
  $("#generateBtn").click();
});

$("#useTranscript").addEventListener("click", () => {
  if (!state.transcript) {
    note("请先运行“AI 拆解与转写”");
    return;
  }
  $("#script").value = state.transcript;
  $("#script").dispatchEvent(new Event("input"));
  note("已将机器转写放入口播文案，请先校对");
});

function showKnowledgeResults(data) {
  const container = $("#knowledgeResults");
  const nodes = [];
  for (const item of data.results || []) {
    const row = document.createElement("div");
    row.className = "knowledge-item";
    const title = document.createElement("b");
    title.textContent = item.title || "未命名资料";
    const source = document.createElement("small");
    source.textContent = item.source === "getnote" ? "得到大脑" : "Obsidian";
    const copy = document.createElement("div");
    copy.textContent = item.content || "";
    row.append(title, source, copy);
    nodes.push(row);
  }
  for (const item of data.errors || []) {
    const error = document.createElement("div");
    error.className = "knowledge-error";
    error.textContent = `${item.source}：${item.error}`;
    nodes.push(error);
  }
  if (!nodes.length) {
    const empty = document.createElement("div");
    empty.textContent = "没有找到相关内容，请换一组更具体的关键词。";
    nodes.push(empty);
  }
  container.replaceChildren(...nodes);
}

$("#knowledgeBtn").addEventListener("click", async () => {
  const query = $("#knowledgeQuery").value.trim();
  if (!query) {
    note("请先输入知识检索关键词");
    return;
  }
  const button = $("#knowledgeBtn");
  button.disabled = true;
  $("#knowledgeState").textContent = "正在检索";
  try {
    const response = await apiFetch("/api/knowledge/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        include_getnote: $("#includeGetnote").checked,
        include_obsidian: $("#includeObsidian").checked,
        limit: 5
      })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "知识检索失败");
    state.knowledgeResults = data.results || [];
    showKnowledgeResults(data);
    $("#knowledgeState").textContent = `找到 ${state.knowledgeResults.length} 条依据`;
    note(`内容大脑检索完成：${state.knowledgeResults.length} 条`);
  } catch (error) {
    $("#knowledgeState").textContent = "检索失败";
    showKnowledgeResults({ errors: [{ source: "engine", error: error.message }] });
    note(`错误：${error.message}`);
  } finally {
    button.disabled = false;
  }
});

$("#tagBtn").addEventListener("click", () => {
  const title = $("#title").value.trim();
  const core = title.replace(/[，。！？、,.!?]/g, " ").split(/\s+/).filter(Boolean).slice(0, 4);
  const tags = [...new Set([...core, "AI视频", "智能体", "自动剪辑", "内容获客"])];
  $("#tags").value = tags.join(", ");
  const nodes = tags.slice(0, 6).map(item => {
    const span = document.createElement("span");
    span.textContent = item;
    return span;
  });
  $("#keywords").replaceChildren(...nodes);
  note("标题、标签和关键词已更新");
});

$("#script").addEventListener("input", () => {
  $("#charCount").textContent = `${$("#script").value.replace(/\s/g, "").length} 字`;
});
$("#script").dispatchEvent(new Event("input"));

$("#openRuns").addEventListener("click", () => {
  if (API_ORIGIN) {
    window.open("https://github.com/yanruwill-dot/yanru-ai-video-agent/releases", "_blank", "noopener");
    return;
  }
  note("产物目录：当前项目的 runs/ 文件夹");
});

function openConnectionSheet() {
  $("#apiOriginInput").value = API_ORIGIN || "";
  $("#apiKeyInput").value = API_KEY || "";
  $("#connectionSheet").classList.add("open");
  $("#connectionSheet").setAttribute("aria-hidden", "false");
}

function closeConnectionSheet() {
  $("#connectionSheet").classList.remove("open");
  $("#connectionSheet").setAttribute("aria-hidden", "true");
}

$("#connectionBtn").addEventListener("click", openConnectionSheet);
$("#closeConnection").addEventListener("click", closeConnectionSheet);
$("#saveConnection").addEventListener("click", async () => {
  const origin = $("#apiOriginInput").value.trim().replace(/\/$/, "");
  const key = $("#apiKeyInput").value.trim();
  if (!origin || !isAllowedConnectionOrigin(origin)) {
    $("#connectionState").textContent = "请输入完整的 HTTPS 地址，例如 https://video-api.example.com";
    $("#connectionState").classList.add("error");
    return;
  }
  const resolved = resolveOrigin(origin);
  if (!/^https:\/\//.test(resolved) && !/^http:\/\/(127\.0\.0\.1|localhost)/.test(resolved)) {
    $("#connectionState").textContent = "手机端只能使用 HTTPS 地址。";
    $("#connectionState").classList.add("error");
    return;
  }
  requestedOrigin = origin;
  API_ORIGIN = resolved;
  API_KEY = key;
  localStorage.setItem("video-agent-api", API_ORIGIN);
  localStorage.setItem("video-agent-key", API_KEY);
  const connected = await health();
  if (!connected) return;
  await loadVoices().catch(error => note(`声音库：${error.message}`));
  await loadLatest();
  closeConnectionSheet();
  note(`生成引擎已切换：${API_ORIGIN}`);
});

const dockLinks = [...document.querySelectorAll(".mobile-dock a")];
dockLinks.forEach(link => {
  link.addEventListener("click", () => {
    dockLinks.forEach(item => item.classList.toggle("active", item === link));
  });
});

if ("IntersectionObserver" in window) {
  const sections = dockLinks.map(link => document.querySelector(link.getAttribute("href"))).filter(Boolean);
  const observer = new IntersectionObserver(entries => {
    const visible = entries
      .filter(entry => entry.isIntersecting)
      .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
    if (!visible) return;
    dockLinks.forEach(link => link.classList.toggle("active", link.getAttribute("href") === `#${visible.target.id}`));
  }, { rootMargin: "-20% 0px -62% 0px", threshold: [0.05, 0.35] });
  sections.forEach(section => observer.observe(section));
}

health().then(connected => {
  if (!connected && matchMedia("(max-width: 900px)").matches && !savedOrigin && !connection.get("api")) {
    openConnectionSheet();
  }
});
loadVoices().catch(error => note(`声音库：${error.message}`));
loadLatest();
