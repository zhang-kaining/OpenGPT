from __future__ import annotations

from app.services.file_memory import render_prompt_section
from app.services.skill_manager import get_skill_manager


def build_system_prompt(memories: list[dict]) -> str:
    skill_mgr = get_skill_manager()
    prompt = (
        "你是一个智能助手，能够帮助用户解答问题、分析信息、使用各种工具完成任务。\n"
        "回答时请使用 Markdown 格式，代码使用代码块，重要内容加粗。\n"
        "当你使用网页搜索结果时，请在回答中用 [数字] 标注引用来源，例如 [1]、[2]。\n"
    )

    controller_mem_text = render_prompt_section("controller_memory")
    if controller_mem_text:
        prompt += f"\n{controller_mem_text}\n"

    if memories:
        mem_text = "\n".join(f"- {memory['memory']}" for memory in memories)
        prompt += f"\n关于用户的近期记忆信息（请在回答时参考）：\n{mem_text}\n"

    skill_summary = skill_mgr.get_summary_prompt()
    if skill_summary:
        prompt += skill_summary

    return prompt
