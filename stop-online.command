#!/bin/zsh
set -euo pipefail

STATE_DIR="${HOME}/.yanru-video-agent"

for pid_file in "${STATE_DIR}/tunnel.pid" "${STATE_DIR}/engine.pid"; do
  if [[ -f "$pid_file" ]]; then
    saved_pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [[ "$saved_pid" == <-> ]] && kill -0 "$saved_pid" 2>/dev/null; then
      kill "$saved_pid" 2>/dev/null || true
    fi
    rm -f "$pid_file"
  fi
done

echo "AI 视频工作台已停止。"
