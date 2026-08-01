#!/bin/zsh
set -euo pipefail

cd "$(dirname "$0")"

DIST_DIR="$PWD/dist"
APP_PATH="${DIST_DIR}/AI视频工作台.app"
RESOURCE_DIR="${APP_PATH}/Contents/Resources/workbench"
ZIP_PATH="${DIST_DIR}/AI视频智能体-v2.0.0-macOS.zip"

rm -rf "$APP_PATH"
mkdir -p "$DIST_DIR"

osacompile -o "$APP_PATH" launcher/main.applescript
mkdir -p "$RESOURCE_DIR"

for item in \
  app.py pipeline.py voice_clone.py knowledge.py runtime_config.py requirements.txt \
  start.command start-online.command stop-online.command \
  install-persistent.command uninstall-persistent.command \
  static README.md API.md ARCHITECTURE.md CHANGELOG.md EDITING_STYLE_RESEARCH.md
do
  ditto "$item" "${RESOURCE_DIR}/${item}"
done

chmod +x \
  "${RESOURCE_DIR}/start.command" \
  "${RESOURCE_DIR}/start-online.command" \
  "${RESOURCE_DIR}/stop-online.command" \
  "${RESOURCE_DIR}/install-persistent.command" \
  "${RESOURCE_DIR}/uninstall-persistent.command"

codesign --force --deep --sign - "$APP_PATH"

rm -f "$ZIP_PATH"
ditto -c -k --sequesterRsrc --keepParent "$APP_PATH" "$ZIP_PATH"

echo "$APP_PATH"
echo "$ZIP_PATH"
