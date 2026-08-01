const STORAGE_API = "video-agent-api";
const STORAGE_KEY = "video-agent-key";

function normalizeBase(value) {
  return String(value || "").trim().replace(/\/+$/, "");
}

function isValidBase(value) {
  const base = normalizeBase(value);
  return /^https:\/\/[A-Za-z0-9.-]+(?::\d+)?$/.test(base)
    || /^http:\/\/(127\.0\.0\.1|localhost)(?::\d+)?$/.test(base);
}

function getConnection() {
  return {
    base: normalizeBase(wx.getStorageSync(STORAGE_API)),
    key: String(wx.getStorageSync(STORAGE_KEY) || "")
  };
}

function saveConnection(base, key) {
  const normalized = normalizeBase(base);
  if (!isValidBase(normalized)) throw new Error("请输入完整的 HTTPS 引擎地址");
  wx.setStorageSync(STORAGE_API, normalized);
  wx.setStorageSync(STORAGE_KEY, String(key || "").trim());
  return { base: normalized, key: String(key || "").trim() };
}

function request(path, options = {}) {
  const { base, key } = getConnection();
  if (!base) return Promise.reject(new Error("请先连接 HTTPS 生成引擎"));
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${base}${path}`,
      method: options.method || "GET",
      data: options.data,
      timeout: options.timeout || 30000,
      header: {
        "Content-Type": options.contentType || "application/json",
        ...(key ? { "X-Video-Agent-Key": key } : {})
      },
      success(response) {
        if (response.statusCode >= 200 && response.statusCode < 300) {
          resolve(response.data);
          return;
        }
        reject(new Error(response.data?.error || `请求失败（${response.statusCode}）`));
      },
      fail(error) {
        reject(new Error(error.errMsg || "网络连接失败"));
      }
    });
  });
}

function uploadFile(tempFilePath, endpoint, name) {
  const { base, key } = getConnection();
  if (!base) return Promise.reject(new Error("请先连接 HTTPS 生成引擎"));
  return new Promise((resolve, reject) => {
    wx.uploadFile({
      url: `${base}${endpoint}?name=${encodeURIComponent(name)}`,
      filePath: tempFilePath,
      name: "file",
      timeout: 120000,
      header: key ? { "X-Video-Agent-Key": key } : {},
      success(response) {
        let payload = {};
        try {
          payload = JSON.parse(response.data || "{}");
        } catch (_) {
          reject(new Error("上传接口返回了无法识别的数据"));
          return;
        }
        if (response.statusCode >= 200 && response.statusCode < 300) {
          resolve(payload);
          return;
        }
        reject(new Error(payload.error || `上传失败（${response.statusCode}）`));
      },
      fail(error) {
        reject(new Error(error.errMsg || "上传失败"));
      }
    });
  });
}

function assetUrl(jobId, name) {
  const { base, key } = getConnection();
  const query = key ? `?key=${encodeURIComponent(key)}` : "";
  return `${base}/runs/${encodeURIComponent(jobId)}/${encodeURIComponent(name)}${query}`;
}

module.exports = {
  assetUrl,
  getConnection,
  isValidBase,
  request,
  saveConnection,
  uploadFile
};
