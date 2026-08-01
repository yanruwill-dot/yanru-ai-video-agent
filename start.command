#!/bin/zsh
set -e
cd "$(dirname "$0")"
exec python3 app.py --host 127.0.0.1 --port 8788
