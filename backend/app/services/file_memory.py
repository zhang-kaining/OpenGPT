import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

FILE_MEMORY_DIR = Path(os.environ.get("FILE_MEMORY_DIR", "data/file_memories"))

# Spec definition
FILE_MEMORY_SPECS = {
    "controller_memory": {
        "name": "controller_memory",
        "title": "主控记忆",
        "filename": "controller_memory.md",
        "max_lines": 200,
        "enabled_for_prompt": True,
        "visible_in_frontend": True,
        "description": "主控模型维护的高置信长期记忆，参与系统提示词",
    }
}

# Regex to parse a line
# Format: - [2026-04-03 23:10] [id:12345678] [P3] [preference] text
LINE_REGEX = re.compile(r"^\-\s+\[(.*?)\]\s+\[id:(.*?)\]\s+\[(P[1-3])\]\s+\[(.*?)\]\s+(.*)$")

def _get_file_path(name: str) -> Path:
    spec = FILE_MEMORY_SPECS.get(name)
    if not spec:
        raise ValueError(f"Unknown file memory spec: {name}")
    FILE_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    return FILE_MEMORY_DIR / spec["filename"]

def list_memory_files() -> List[Dict[str, Any]]:
    return list(FILE_MEMORY_SPECS.values())

def read_memory_file(name: str) -> List[Dict[str, Any]]:
    path = _get_file_path(name)
    if not path.exists():
        return []
    
    lines = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        match = LINE_REGEX.match(raw_line)
        if match:
            lines.append({
                "time": match.group(1),
                "id": match.group(2),
                "priority": match.group(3),
                "kind": match.group(4),
                "text": match.group(5).strip(),
                "raw": raw_line
            })
    return lines

def _write_memory_file(name: str, lines: List[Dict[str, Any]]) -> None:
    path = _get_file_path(name)
    content = "\n".join(
        f"- [{line['time']}] [id:{line['id']}] [{line['priority']}] [{line['kind']}] {line['text']}"
        for line in lines
    )
    path.write_text(content + "\n", encoding="utf-8")

def _generate_id() -> str:
    return uuid.uuid4().hex[:8]

def _get_current_time() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")

def enforce_line_limit(name: str, max_lines: int = 200) -> None:
    lines = read_memory_file(name)
    if len(lines) <= max_lines:
        return
    
    # Needs pruning
    # Priority: P3 -> P2 -> P1
    # Within same priority, oldest first
    # Sort by priority (P3 > P2 > P1 for deletion), then by time (oldest first)
    # P3 is 'P3', P2 is 'P2', P1 is 'P1'. So reverse sort priority means P3 comes first.
    
    # We want to keep the newest and highest priority.
    # Let's sort lines so that the ones to DELETE are at the BEGINNING.
    # Priority: P3 > P2 > P1 (so P3 is deleted first)
    # Time: oldest > newest (so oldest is deleted first)
    
    def sort_key(line):
        # priority: P3 -> 3, P2 -> 2, P1 -> 1. We want P3 to be deleted first, so it should be smaller in sort?
        # Actually, let's sort by (priority_num descending, time ascending)
        # priority_num: P3 -> 3, P2 -> 2, P1 -> 1
        p_num = int(line["priority"][1]) if line["priority"].startswith("P") and len(line["priority"]) == 2 else 3
        return (p_num, line["time"])
    
    sorted_lines = sorted(lines, key=sort_key)
    
    # Delete the first (len(lines) - max_lines) lines
    to_delete_ids = set(line["id"] for line in sorted_lines[:len(lines) - max_lines])
    
    new_lines = [line for line in lines if line["id"] not in to_delete_ids]
    _write_memory_file(name, new_lines)

def append_memory_line(name: str, text: str, priority: str = "P3", kind: str = "fact") -> str:
    lines = read_memory_file(name)
    
    # Deduplication: if text already exists, update its time and priority
    for line in lines:
        if line["text"] == text.strip():
            line["time"] = _get_current_time()
            line["priority"] = priority
            line["kind"] = kind
            _write_memory_file(name, lines)
            return line["id"]
            
    line_id = _generate_id()
    lines.append({
        "time": _get_current_time(),
        "id": line_id,
        "priority": priority,
        "kind": kind,
        "text": text.strip()
    })
    _write_memory_file(name, lines)
    
    spec = FILE_MEMORY_SPECS.get(name)
    if spec and "max_lines" in spec:
        enforce_line_limit(name, spec["max_lines"])
        
    return line_id

def update_memory_line(name: str, line_id: str, text: str, priority: str, kind: str) -> bool:
    lines = read_memory_file(name)
    for line in lines:
        if line["id"] == line_id:
            line["text"] = text.strip()
            line["priority"] = priority
            line["kind"] = kind
            _write_memory_file(name, lines)
            return True
    return False

def delete_memory_line(name: str, line_id: str) -> bool:
    lines = read_memory_file(name)
    new_lines = [line for line in lines if line["id"] != line_id]
    if len(new_lines) < len(lines):
        _write_memory_file(name, new_lines)
        return True
    return False

def promote_memory_line(name: str, line_id: str, priority: str = "P1") -> bool:
    lines = read_memory_file(name)
    for line in lines:
        if line["id"] == line_id:
            line["priority"] = priority
            _write_memory_file(name, lines)
            return True
    return False

def render_prompt_section(name: str) -> str:
    spec = FILE_MEMORY_SPECS.get(name)
    if not spec or not spec.get("enabled_for_prompt"):
        return ""
        
    lines = read_memory_file(name)
    if not lines:
        return ""
        
    res = [f"## {spec['title']}"]
    for line in lines:
        res.append(f"- [{line['time']}] {line['text']}")
    return "\n".join(res) + "\n"
