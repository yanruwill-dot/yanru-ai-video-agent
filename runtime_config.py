from __future__ import annotations

import os
from pathlib import Path


def load_settings() -> dict[str, str]:
    values = dict(os.environ)
    env_file = Path(__file__).resolve().parent / ".env"
    if not env_file.is_file():
        return values
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values.setdefault(key.strip(), value.strip().strip("\"'"))
    return values
