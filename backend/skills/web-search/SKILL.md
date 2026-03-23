---
name: web-search
description: 搜索互联网获取实时信息、新闻、最新数据
enabled: true
requires_env: [TAVILY_API_KEY]
---

当用户询问实时信息、新闻、近期事件，或你的训练数据可能过时的内容时，调用 web_search 工具。

工具参数：
- query（必填）：搜索关键词，应简洁精准，使用中文或英文均可

搜索完成后，请在回答中用 [数字] 标注引用来源，例如 [1]、[2]。