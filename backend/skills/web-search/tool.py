from app.services import web_search as web_search_service


def web_search(query: str) -> str:
    """搜索互联网获取最新信息。当用户询问实时数据、新闻、近期事件时使用。"""
    results = web_search_service.search(query)
    if not results:
        return "未找到相关搜索结果。"
    lines = ["以下是搜索结果，请基于这些内容回答，并在回答中用 [数字] 标注引用来源：\n"]
    for r in results:
        lines.append(f"[{r['index']}] 标题: {r['title']}")
        lines.append(f"    URL: {r['url']}")
        lines.append(f"    内容: {r['content']}\n")
    return "\n".join(lines)
