import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.tool_result_normalizer import (
    build_mcp_tool_start_events,
    extract_bing_search_citations,
    normalize_mcp_tool_result,
)


_RAW_BING_RESULT = r"""[{'type': 'text', 'text': '{\n  "query": "上海今天天气",\n  "results": [\n    {\n      "uuid": "08afa9e2-1605-4dc0-9180-1c907b137e1b",\n      "title": "上海天气预报",\n      "url": "https://www.weather.com.cn/weather/101020100.shtml",\n      "snippet": "上海天气预报，及时准确发布中央气象台天气信息。",\n      "displayUrl": "https://www.weather.com.cn › weather"\n    },\n    {\n      "uuid": "501a46fb-9ac4-4d58-a270-508e855e6af7",\n      "title": "上海24小时天气查询",\n      "url": "https://tianqi.2345.com/today-58362.htm",\n      "snippet": "2345天气预报为您提供上海24小时天气详情。",\n      "displayUrl": "https://tianqi.2345.com"\n    }\n  ],\n  "totalResults": 22700\n}', 'id': 'lc_b8705069-905a-4a2d-9f33-ed8b50bb3937'}]"""


class ToolResultNormalizerTests(unittest.TestCase):
    def test_extracts_citations_from_mcp_wrapped_bing_result(self):
        result = extract_bing_search_citations(_RAW_BING_RESULT, offset=3)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["index"], 4)
        self.assertEqual(result[0]["title"], "上海天气预报")
        self.assertEqual(
            result[0]["url"],
            "https://www.weather.com.cn/weather/101020100.shtml",
        )
        self.assertIn("中央气象台", result[0]["content"])
        self.assertEqual(result[1]["index"], 5)

    def test_returns_empty_list_for_unparseable_result(self):
        self.assertEqual(extract_bing_search_citations("not-json"), [])

    def test_bing_search_uses_searching_event(self):
        events = build_mcp_tool_start_events("bing_search", {"query": "上海天气"})
        self.assertEqual(events, [{"type": "searching", "query": "上海天气"}])

    def test_normalized_bing_result_contains_citations_and_search_results_event(self):
        normalized = normalize_mcp_tool_result(
            "bing_search",
            _RAW_BING_RESULT,
            citation_offset=1,
        )

        self.assertEqual(len(normalized.citations), 2)
        self.assertEqual(normalized.citations[0]["index"], 2)
        self.assertEqual(normalized.sse_events[0]["type"], "search_results")
        self.assertIn("[2] 标题: 上海天气预报", normalized.content)


if __name__ == "__main__":
    unittest.main()
