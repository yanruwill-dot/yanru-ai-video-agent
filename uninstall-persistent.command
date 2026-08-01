#!/bin/zsh
set -euo pipefail

LABEL="com.yanru.video-agent"
PLIST_PATH="${HOME}/Library/LaunchAgents/${LABEL}.plist"
USER_DOMAIN="gui/$(id -u)"

launchctl bootout "$USER_DOMAIN/$LABEL" >/dev/null 2>&1 || true

if [[ -f "$PLIST_PATH" ]]; then
  TRASH_DIR="${HOME}/.Trash/YanruVideoAgent-$(date +%Y%m%d-%H%M%S)"
  mkdir -p "$TRASH_DIR"
  mv "$PLIST_PATH" "$TRASH_DIR/"
  echo "常驻服务已停止，配置已移到废纸篓：${TRASH_DIR}"
else
  echo "常驻服务已停止。"
fi
