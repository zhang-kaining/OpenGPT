import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.mcp_manager import _lc_tool_to_openai_definition


class _FakeDictSchemaTool:
    name = "bing_search"
    description = "bing tool"
    args_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词",
            },
            "count": {
                "type": "number",
                "default": 10,
            },
        },
        "required": ["query"],
    }


class _FakeModelSchema:
    @staticmethod
    def model_json_schema():
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "title": "Query",
                    "description": "搜索关键词",
                }
            },
            "required": ["query"],
            "title": "SearchInput",
        }


class _FakeModelSchemaTool:
    name = "bing_search"
    description = "bing tool"
    args_schema = _FakeModelSchema


class McpManagerSchemaTests(unittest.TestCase):
    def test_preserves_parameters_when_args_schema_is_dict(self):
        result = _lc_tool_to_openai_definition(_FakeDictSchemaTool())
        self.assertEqual(
            result["function"]["parameters"]["properties"]["query"]["type"],
            "string",
        )
        self.assertEqual(
            result["function"]["parameters"]["required"],
            ["query"],
        )

    def test_uses_model_json_schema_when_available(self):
        result = _lc_tool_to_openai_definition(_FakeModelSchemaTool())
        self.assertEqual(
            result["function"]["parameters"]["properties"]["query"]["description"],
            "搜索关键词",
        )
        self.assertNotIn("title", result["function"]["parameters"]["properties"]["query"])


if __name__ == "__main__":
    unittest.main()
