#!/bin/zsh
set -euo pipefail

cd "$(dirname "$0")"

STATE_DIR="${HOME}/.yanru-video-agent"
ENGINE_LOG="${STATE_DIR}/engine.log"
TUNNEL_LOG="${STATE_DIR}/tunnel.log"
ENGINE_PID_FILE="${STATE_DIR}/engine.pid"
TUNNEL_PID_FILE="${STATE_DIR}/tunnel.pid"
URL_FILE="${STATE_DIR}/online-url.txt"
ONLINE_PORT="${VIDEO_AGENT_ONLINE_PORT:-8789}"

mkdir -p "$STATE_DIR"

stop_pid_file() {
  local pid_file="$1"
  if [[ -f "$pid_file" ]]; then
    local saved_pid
    saved_pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [[ "$saved_pid" == <-> ]] && kill -0 "$saved_pid" 2>/dev/null; then
      kill "$saved_pid" 2>/dev/null || true
    fi
    rm -f "$pid_file"
  fi
}

if ! command -v python3 >/dev/null 2>&1; then
  echo "没有找到 Python 3，无法启动视频引擎。"
  exit 1
fi
if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
  echo "没有找到 FFmpeg。请先运行：brew install ffmpeg"
  exit 1
fi
if ! command -v cloudflared >/dev/null 2>&1; then
  echo "没有找到 Cloudflare Tunnel。请先运行：brew install cloudflared"
  exit 1
fi
if ! python3 -c "import PIL" >/dev/null 2>&1; then
  python3 -m pip install -r requirements.txt
fi

stop_pid_file "$TUNNEL_PID_FILE"
stop_pid_file "$ENGINE_PID_FILE"

API_KEY="$(openssl rand -hex 24)"
: > "$ENGINE_LOG"
: > "$TUNNEL_LOG"

nohup env VIDEO_AGENT_API_KEY="$API_KEY" python3 app.py --host 127.0.0.1 --port "$ONLINE_PORT" \
  >"$ENGINE_LOG" 2>&1 &
ENGINE_PID=$!
echo "$ENGINE_PID" > "$ENGINE_PID_FILE"

for _ in {1..30}; do
  if curl -fsS -H "X-Video-Agent-Key: ${API_KEY}" \
    "http://127.0.0.1:${ONLINE_PORT}/api/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.25
done
if ! curl -fsS -H "X-Video-Agent-Key: ${API_KEY}" \
  "http://127.0.0.1:${ONLINE_PORT}/api/health" >/dev/null 2>&1; then
  echo "本地视频引擎启动失败，日志：${ENGINE_LOG}"
  exit 1
fi

nohup cloudflared tunnel --no-autoupdate --url "http://127.0.0.1:${ONLINE_PORT}" \
  >"$TUNNEL_LOG" 2>&1 &
TUNNEL_PID=$!
echo "$TUNNEL_PID" > "$TUNNEL_PID_FILE"

TUNNEL_URL=""
for _ in {1..60}; do
  TUNNEL_URL="$(grep -Eo 'https://[A-Za-z0-9-]+\.trycloudflare\.com' "$TUNNEL_LOG" | tail -1 || true)"
  [[ -n "$TUNNEL_URL" ]] && break
  sleep 0.5
done
if [[ -z "$TUNNEL_URL" ]]; then
  echo "HTTPS 隧道启动失败，日志：${TUNNEL_LOG}"
  exit 1
fi

ONLINE_URL="${TUNNEL_URL}/#key=${API_KEY}"
printf '%s\n' "$ONLINE_URL" > "$URL_FILE"

echo
echo "AI 视频工作台已经在线："
echo "$ONLINE_URL"
echo
echo "保持这台 Mac 开机并保留此服务进程即可使用。"
echo "停止服务请双击 stop-online.command，或在此窗口按 Control-C。"

if [[ "${VIDEO_AGENT_NO_OPEN:-0}" != "1" ]]; then
  open "$ONLINE_URL"
fi

cleanup() {
  stop_pid_file "$TUNNEL_PID_FILE"
  stop_pid_file "$ENGINE_PID_FILE"
}
trap cleanup EXIT INT TERM

if [[ "${VIDEO_AGENT_DETACH:-0}" != "1" ]]; then
  wait "$TUNNEL_PID"
fi
