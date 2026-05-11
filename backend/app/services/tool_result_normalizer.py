from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NormalizedToolResult:
    content: str
    citations: list[dict]
    sse_events: list[dict]


def build_mcp_tool_start_events(tool_name: str, args: dict) -> list[dict]:
    query = str(args.get("query") or "").strip()
    if tool_name == "bing_search" and query:
        return [{"type": "searching", "query": query}]
    return [{"type": "tool_call", "name": tool_name, "status": "running"}]


def normalize_mcp_tool_result(
    tool_name: str,
    raw_content: str,
    citation_offset: int = 0,
) -> NormalizedToolResult:
    if tool_name == "bing_search":
        citations = extract_bing_search_citations(raw_content, citation_offset)
        if citations:
            return NormalizedToolResult(
                content=format_search_results(citations),
                citations=citations,
                sse_events=[{"type": "search_results", "results": citations}],
            )
    return NormalizedToolResult(content=raw_content, citations=[], sse_events=[])


def format_search_results(results: list[dict]) -> str:
    if not results:
        return "未找到相关搜索结果。"
    lines = ["以下是搜索结果，请基于这些内容回答，并在回答中用 [数字] 标注引用来源：\n"]
    for r in results:
        lines.append(f"[{r['index']}] 标题: {r['title']}")
        lines.append(f"    URL: {r['url']}")
        lines.append(f"    内容: {r['content']}\n")
    return "\n".join(lines)


def extract_bing_search_citations(raw_content: str, offset: int = 0) -> list[dict]:
    payload = _extract_bing_search_payload(raw_content)
    if not payload:
        return []

    citations: list[dict] = []
    for item in payload.get("results", []) or []:
        if not isinstance(item, dict):
            continue
        citation = _normalize_search_citation(item, offset + len(citations) + 1)
        if citation:
            citations.append(citation)
    return citations


def _extract_bing_search_payload(raw_content: str) -> dict | None:
    parsed = _parse_json_or_python(raw_content)
    payload = _unwrap_bing_payload(parsed)
    if payload:
        return payload

    if isinstance(raw_content, str):
        return _unwrap_bing_payload(raw_content)
    return None


def _unwrap_bing_payload(value: Any) -> dict | None:
    if isinstance(value, dict):
        results = value.get("results")
        if isinstance(results, list):
            return value
        text = value.get("text")
        if isinstance(text, str):
            nested = _parse_json_or_python(text)
            if isinstance(nested, dict) and isinstance(nested.get("results"), list):
                return nested
        return None

    if isinstance(value, list):
        for item in value:
            payload = _unwrap_bing_payload(item)
            if payload:
                return payload
        return None

    if isinstance(value, str):
        nested = _parse_json_or_python(value)
        if nested is not None and nested is not value:
            return _unwrap_bing_payload(nested)

    return None


def _parse_json_or_python(value: str):
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return None

    try:
        return json.loads(text)
    except Exception:
        pass

    try:
        return ast.literal_eval(text)
    except Exception:
        return value


def _normalize_search_citation(item: dict, index: int) -> dict | None:
    url = str(item.get("url") or "").strip()
    if not url:
        return None

    citation = {
        "index": index,
        "title": str(item.get("title") or url).strip(),
        "url": url,
        "content": str(
            item.get("snippet")
            or item.get("content")
            or item.get("summary")
            or ""
        ).strip(),
    }
    score = item.get("score")
    if isinstance(score, (int, float)):
        citation["score"] = score
    return citation
