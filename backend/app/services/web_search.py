from tavily import TavilyClient
from app.config import get_settings

settings = get_settings()

_client: TavilyClient | None = None


def get_tavily_client() -> TavilyClient:
    global _client
    if _client is None:
        _client = TavilyClient(api_key=settings.tavily_api_key)
    return _client


def search(query: str, max_results: int = 5) -> list[dict]:
    """执行网页搜索，返回结构化结果列表"""
    if not settings.tavily_api_key:
        return []
    client = get_tavily_client()
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
