#!/bin/zsh
set -euo pipefail

cd "$(dirname "$0")"

LABEL="com.yanru.video-agent"
APP_ROOT="${HOME}/Library/Application Support/YanruVideoAgent/workbench"
STATE_DIR="${HOME}/Library/Application Support/YanruVideoAgent/state"
PLIST_PATH="${HOME}/Library/LaunchAgents/${LABEL}.plist"
PYTHON_BIN="$(command -v python3)"
USER_DOMAIN="gui/$(id -u)"

if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
  echo "没有找到 FFmpeg。请先运行：brew install ffmpeg"
  exit 1
fi
if ! "$PYTHON_BIN" -c "import PIL" >/dev/null 2>&1; then
  "$PYTHON_BIN" -m pip install -r requirements.txt
fi

mkdir -p "$APP_ROOT" "$STATE_DIR" "${HOME}/Library/LaunchAgents"

for item in \
  app.py pipeline.py voice_clone.py knowledge.py runtime_config.py requirements.txt \
  start.command start-online.command stop-online.command \
  install-persistent.command uninstall-persistent.command \
  static launcher README.md API.md ARCHITECTURE.md CHANGELOG.md EDITING_STYLE_RESEARCH.md
do
  ditto "$item" "${APP_ROOT}/${item}"
done

if [[ -f .env ]]; then
  ditto .env "${APP_ROOT}/.env"
fi

sed \
  -e "s|__PYTHON__|${PYTHON_BIN}|g" \
  -e "s|__APP_ROOT__|${APP_ROOT}|g" \
  -e "s|__STATE_DIR__|${STATE_DIR}|g" \
  launcher/com.yanru.video-agent.plist > "$PLIST_PATH"

plutil -lint "$PLIST_PATH" >/dev/null
launchctl bootout "$USER_DOMAIN/$LABEL" >/dev/null 2>&1 || true
launchctl bootstrap "$USER_DOMAIN" "$PLIST_PATH"
launchctl kickstart -k "$USER_DOMAIN/$LABEL"

for _ in {1..40}; do
  if curl -fsS "http://127.0.0.1:8788/api/health" >/dev/null 2>&1; then
    echo "长期生成引擎已连接：http://127.0.0.1:8788/"
    exit 0
  fi
  sleep 0.25
done

echo "长期生成引擎启动失败，日志：${STATE_DIR}/engine-error.log"
exit 1
