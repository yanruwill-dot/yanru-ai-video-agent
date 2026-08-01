from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from runtime_config import load_settings


class KnowledgeError(RuntimeError):
    pass


def engine_status() -> dict[str, object]:
    vault = load_settings().get("VIDEO_AGENT_OBSIDIAN_VAULT", "").strip()
    return {
        "obsidian_configured": bool(vault and Path(vault).expanduser().is_dir()),
        "getnote_configured": shutil.which("getnote") is not None,
    }


def _query_terms(query: str) -> list[str]:
    compact = re.sub(r"\s+", " ", query.strip()).casefold()
    if not compact:
        raise KnowledgeError("知识检索关键词不能为空")
    terms = [part for part in re.split(r"[\s,，。;；:：/]+", compact) if len(part) >= 2]
    return list(dict.fromkeys([compact, *terms]))


def _snippet(content: str, terms: list[str], width: int = 180) -> str:
    folded = content.casefold()
    positions = [folded.find(term) for term in terms if folded.find(term) >= 0]
    start = max(0, (min(positions) if positions else 0) - width // 3)
    value = re.sub(r"\s+", " ", content[start:start + width]).strip()
    return value


def search_obsidian(vault: Path, query: str, limit: int = 5) -> list[dict[str, object]]:
    vault = vault.expanduser().resolve()
    if not vault.is_dir():
        raise KnowledgeError(f"Obsidian 目录不存在：{vault}")
    terms = _query_terms(query)
    max_files = int(load_settings().get("VIDEO_AGENT_OBSIDIAN_MAX_FILES", "6000"))
    rows: list[tuple[int, Path, str]] = []
    for index, path in enumerate(vault.rglob("*.md")):
        if index >= max_files:
            break
        if any(part.startswith(".") for part in path.relative_to(vault).parts):
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        folded = f"{path.stem}\n{content}".casefold()
        score = sum((folded.count(term) * max(2, len(term))) for term in terms)
        if score:
            rows.append((score, path, content))
    rows.sort(key=lambda item: (-item[0], str(item[1])))
    return [
        {
            "source": "obsidian",
            "title": path.stem,
            "content": _snippet(content, terms),
            "path": str(path),
            "score": score,
        }
        for score, path, content in rows[:limit]
    ]


def search_getnote(query: str, limit: int = 5) -> list[dict[str, object]]:
    executable = shutil.which("getnote")
    if not executable:
        raise KnowledgeError("未找到 getnote CLI")
    result = subprocess.run(
        [executable, "search", query.strip(), "--limit", str(limit), "-o", "json"],
        text=True,
        capture_output=True,
        timeout=45,
    )
    if result.returncode:
        raise KnowledgeError((result.stderr or result.stdout or "得到大脑检索失败")[-1200:])
    try:
        payload = json.loads(result.stdout)
        values = payload["data"]["results"] if payload.get("success") else []
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise KnowledgeError("getnote CLI 返回了无法识别的数据") from error
    rows = []
    seen: set[tuple[str, str]] = set()
    for item in values:
        note_id = str(item.get("note_id", ""))
        key = (note_id, str(item.get("content", "")))
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "source": "getnote",
                "note_id": note_id,
                "title": str(item.get("title", "未命名笔记")),
                "content": re.sub(r"\s+", " ", str(item.get("content", ""))).strip()[:240],
                "created_at": str(item.get("created_at", "")),
            }
        )
        if len(rows) >= limit:
            break
    return rows


def search_knowledge(
    query: str,
    *,
    include_obsidian: bool = True,
    include_getnote: bool = True,
    vault: str = "",
    limit: int = 5,
) -> dict[str, object]:
    limit = max(1, min(int(limit), 10))
    results: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []
    if include_obsidian:
        vault_value = vault.strip() or load_settings().get("VIDEO_AGENT_OBSIDIAN_VAULT", "").strip()
        if vault_value:
            try:
                results.extend(search_obsidian(Path(vault_value), query, limit))
            except KnowledgeError as error:
                errors.append({"source": "obsidian", "error": str(error)})
        else:
            errors.append({"source": "obsidian", "error": "未配置 VIDEO_AGENT_OBSIDIAN_VAULT"})
    if include_getnote:
        try:
            results.extend(search_getnote(query, limit))
        except (KnowledgeError, subprocess.TimeoutExpired) as error:
            errors.append({"source": "getnote", "error": str(error)})
    return {
        "query": query.strip(),
        "results": results[: limit * 2],
        "errors": errors,
        "sources": {
            "obsidian": sum(item["source"] == "obsidian" for item in results),
            "getnote": sum(item["source"] == "getnote" for item in results),
        },
    }
