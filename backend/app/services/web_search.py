from tavily import TavilyClient
from app.config import get_settings


def search(query: str, max_results: int = 5) -> list[dict]:
    """执行网页搜索，返回结构化结果列表"""
    s = get_settings()
    if not s.tavily_api_key:
        return []
    client = TavilyClient(api_key=s.tavily_api_key)
    response = client.search(
        query=query,
        search_depth="advanced",
        max_results=max_results,
        include_answer=False,
    )
    results = []
    for i, item in enumerate(response.get("results", []), start=1):
        results.append({
            "index": i,
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "content": item.get("content", "")[:800],
            "score": item.get("score", 0),
        })
    return results


TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "搜索互联网获取最新信息。当用户询问实时数据、新闻、近期事件、"
            "或你的训练数据可能过时的内容时，使用此工具。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词，应简洁精准"
                }
            },
            "required": ["query"]
        }
    }
}
