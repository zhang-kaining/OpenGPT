import json
from typing import Optional

from app.services.file_memory import (
    append_memory_line,
    delete_memory_line,
    promote_memory_line,
    read_memory_file,
    update_memory_line,
)

def list_controller_memory() -> str:
    """
    列出当前所有的主控记忆（controller_memory）。
    返回 JSON 格式的字符串，包含 id, time, priority, kind, text。
    """
    lines = read_memory_file("controller_memory")
    return json.dumps(lines, ensure_ascii=False, indent=2)

def remember_important_fact(fact: str, priority: str = "P3", kind: str = "fact") -> str:
    """
    记录一条重要事实到主控记忆中。
    
    参数:
    - fact: 要记录的事实文本，尽量简明扼要。
    - priority: 优先级，可选 P1, P2, P3。P1为最高级（如稳定偏好），P3为最低级（如临时上下文）。默认 P3。
    - kind: 事实类型，如 preference, fact, project, context。默认 fact。
    
    返回:
    - 记录结果及生成的记录 ID。
    """
    if priority not in ["P1", "P2", "P3"]:
        return "错误：priority 必须是 P1, P2 或 P3。"
        
    line_id = append_memory_line("controller_memory", fact, priority, kind)
    return f"成功记录事实，ID: {line_id}"

def update_memory_fact(line_id: str, fact: str, priority: str, kind: str) -> str:
    """
    更新一条已存在的主控记忆。
    
    参数:
    - line_id: 记忆的唯一 ID。
    - fact: 新的文本内容。
    - priority: 新的优先级 (P1, P2, P3)。
    - kind: 新的类型。
    """
    if priority not in ["P1", "P2", "P3"]:
        return "错误：priority 必须是 P1, P2 或 P3。"
        
    success = update_memory_line("controller_memory", line_id, fact, priority, kind)
    if success:
        return f"成功更新记忆 {line_id}。"
    else:
        return f"错误：未找到 ID 为 {line_id} 的记忆。"

def delete_memory_fact(line_id: str) -> str:
    """
    删除一条主控记忆。
    
    参数:
    - line_id: 记忆的唯一 ID。
    """
    success = delete_memory_line("controller_memory", line_id)
    if success:
        return f"成功删除记忆 {line_id}。"
    else:
        return f"错误：未找到 ID 为 {line_id} 的记忆。"

def pin_memory_fact(line_id: str, priority: str = "P1") -> str:
    """
    将一条主控记忆的优先级提升（置顶）。
    
    参数:
    - line_id: 记忆的唯一 ID。
    - priority: 目标优先级，默认为 P1。
    """
    if priority not in ["P1", "P2", "P3"]:
        return "错误：priority 必须是 P1, P2 或 P3。"
        
    success = promote_memory_line("controller_memory", line_id, priority)
    if success:
        return f"成功将记忆 {line_id} 的优先级设置为 {priority}。"
    else:
        return f"错误：未找到 ID 为 {line_id} 的记忆。"
