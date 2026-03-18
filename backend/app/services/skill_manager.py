"""
Skill Manager
=============
扫描 backend/skills/ 目录，加载所有 SKILL.md 和可选的 tool.py。

每个 Skill 目录结构：
    skills/
    └── my-skill/
        ├── SKILL.md    # 必须：frontmatter + 指令
        └── tool.py     # 可选：Python 函数，自动注册为 Function Calling 工具

SKILL.md frontmatter 字段：
    name: str           技能唯一标识
    description: str    一句话描述（注入摘要列表）
    enabled: bool       默认 true
    requires_env: list  需要的环境变量，缺失则自动禁用
"""

from __future__ import annotations

import importlib.util
import inspect
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml

logger = logging.getLogger(__name__)

# skills 目录：backend/skills/
SKILLS_DIR = Path(__file__).parent.parent.parent / "skills"


# ---------- 数据结构 ----------

@dataclass
class SkillTool:
    """一个从 tool.py 注册的可调用工具"""
    name: str                    # 函数名，即工具名
    function: Callable           # 实际函数
    definition: dict             # OpenAI Function Calling JSON Schema


@dataclass
class Skill:
    name: str
    description: str
    enabled: bool
    detail: str                  # SKILL.md 下半截，按需返回给模型
    tools: dict[str, SkillTool] = field(default_factory=dict)


# ---------- 核心逻辑 ----------

class SkillManager:
    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def load(self, skills_dir: Path = SKILLS_DIR) -> None:
        """扫描并加载所有 Skill，幂等，可重复调用"""
        self._skills.clear()
        if not skills_dir.exists():
            logger.warning("skills 目录不存在: %s", skills_dir)
            return

        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            try:
                skill = _parse_skill(skill_dir, skill_md)
                if skill:
                    self._skills[skill.name] = skill
                    tool_count = len(skill.tools)
                    status = "✓" if skill.enabled else "✗ (disabled)"
                    logger.info("Skill [%s] %s  tools=%d", skill.name, status, tool_count)
            except Exception:
                logger.exception("加载 Skill 失败: %s", skill_dir.name)

    # ---------- 查询接口 ----------

    @property
    def enabled_skills(self) -> list[Skill]:
        return [s for s in self._skills.values() if s.enabled]

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def get_summary_prompt(self) -> str:
        """生成注入 System Prompt 的技能摘要列表（轻量）"""
        skills = self.enabled_skills
        if not skills:
            return ""
        lines = ["\n## 可用技能\n以下技能可按需使用，需要时先调用 get_skill_detail 获取详细说明：\n"]
        for s in skills:
            lines.append(f"- **{s.name}**: {s.description}")
        return "\n".join(lines)

    def get_all_tool_definitions(self) -> list[dict]:
        """返回所有已启用 Skill 的工具定义列表（用于初始 tools 注册）"""
        defs = []
        for skill in self.enabled_skills:
            for tool in skill.tools.values():
                defs.append(tool.definition)
        return defs

    def find_tool(self, tool_name: str) -> SkillTool | None:
        """按工具名查找对应的 SkillTool"""
        for skill in self.enabled_skills:
            if tool_name in skill.tools:
                return skill.tools[tool_name]
        return None

    def get_skill_by_tool(self, tool_name: str) -> Skill | None:
        """按工具名反查所属 Skill"""
        for skill in self.enabled_skills:
            if tool_name in skill.tools:
                return skill
        return None

    # ---------- get_skill_detail 工具定义 ----------

    @property
    def get_skill_detail_definition(self) -> dict:
        skill_names = [s.name for s in self.enabled_skills if not s.tools]
        # 只有存在"无工具 Skill"（纯 System Prompt 型）或工具需要延迟加载时才注册此工具
        # 但统一注册更简单，模型可以随时查询
        return {
            "type": "function",
            "function": {
                "name": "get_skill_detail",
                "description": (
                    "获取指定技能的详细使用说明。当你需要使用某个技能但不确定具体操作方式时调用。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "skill_name": {
                            "type": "string",
                            "description": f"技能名称，可选值: {skill_names or [s.name for s in self.enabled_skills]}",
                        }
                    },
                    "required": ["skill_name"],
                },
            },
        }


# ---------- 解析函数 ----------

def _parse_skill(skill_dir: Path, skill_md: Path) -> Skill | None:
    raw = skill_md.read_text(encoding="utf-8")

    # 分割 frontmatter 和正文
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) < 3:
            raise ValueError("SKILL.md frontmatter 格式错误")
        meta = yaml.safe_load(parts[1]) or {}
        detail = parts[2].strip()
    else:
        meta = {}
        detail = raw.strip()

    name: str = meta.get("name") or skill_dir.name
    description: str = meta.get("description", "")
    enabled: bool = bool(meta.get("enabled", True))

    # 检查环境变量依赖
    requires_env: list[str] = meta.get("requires_env", [])
    missing = [e for e in requires_env if not os.environ.get(e)]
    if missing:
        logger.info("Skill [%s] 禁用：缺少环境变量 %s", name, missing)
        enabled = False

    # 加载 tool.py（如果存在）
    tools: dict[str, SkillTool] = {}
    tool_py = skill_dir / "tool.py"
    if tool_py.exists():
        tools = _load_tools_from_file(tool_py, name)

    return Skill(
        name=name,
        description=description,
        enabled=enabled,
        detail=detail,
        tools=tools,
    )


def _load_tools_from_file(tool_py: Path, skill_name: str) -> dict[str, SkillTool]:
    """动态加载 tool.py，把所有公开函数注册为工具"""
    spec = importlib.util.spec_from_file_location(f"skill_{skill_name}", tool_py)
    if not spec or not spec.loader:
        return {}
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]

    tools: dict[str, SkillTool] = {}
    for fn_name, fn in inspect.getmembers(module, inspect.isfunction):
        if fn_name.startswith("_"):
            continue
        definition = _build_tool_definition(fn)
        tools[fn_name] = SkillTool(
            name=fn_name,
            function=fn,
            definition=definition,
        )
    return tools


def _build_tool_definition(fn: Callable) -> dict:
    """从函数签名 + docstring 自动生成 OpenAI Function Calling JSON Schema"""
    sig = inspect.signature(fn)
    doc = inspect.getdoc(fn) or ""

    # 解析 docstring 中的 :param xxx: 描述
    param_docs: dict[str, str] = {}
    for line in doc.splitlines():
        line = line.strip()
        if line.startswith(":param "):
            parts = line[7:].split(":", 1)
            if len(parts) == 2:
                param_docs[parts[0].strip()] = parts[1].strip()

    # 提取函数描述（第一段，去掉 :param 部分）
    description_lines = []
    for line in doc.splitlines():
        if line.strip().startswith(":"):
            break
        description_lines.append(line)
    description = "\n".join(description_lines).strip() or fn.__name__

    # 构建 parameters
    properties: dict[str, Any] = {}
    required: list[str] = []

    _type_map = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
    }

    for pname, param in sig.parameters.items():
        if pname.startswith("_"):  # 以 _ 开头的参数不暴露给模型（框架注入用）
            continue

        ann = param.annotation
        json_type = _type_map.get(ann, "string") if ann != inspect.Parameter.empty else "string"

        prop: dict[str, Any] = {
            "type": json_type,
            "description": param_docs.get(pname, pname),
        }

        if param.default is inspect.Parameter.empty:
            required.append(pname)
        else:
            prop["default"] = param.default

        properties[pname] = prop

    return {
        "type": "function",
        "function": {
            "name": fn.__name__,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


# ---------- 全局单例 ----------

_manager: SkillManager | None = None


def get_skill_manager() -> SkillManager:
    global _manager
    if _manager is None:
        _manager = SkillManager()
        _manager.load()
    return _manager
