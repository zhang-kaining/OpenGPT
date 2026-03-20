"""
飞书写文档 Skill：将内容写入飞书文档（Wiki 页或云空间）。
依赖 FEISHU_APP_ID / FEISHU_APP_SECRET，以及可选 FEISHU_WIKI_NODE_TOKEN 或 FEISHU_DEFAULT_FOLDER_TOKEN。
"""

from app.services import feishu as feishu_service


async def feishu_write_doc(title: str, content: str, as_sub_doc: bool = False) -> str:
    """
    将内容写入飞书文档。若配置了 Wiki：as_sub_doc=False 则追加到当前页；as_sub_doc=True 则在该页下创建子文档（新页面）。

    :param title: 文档标题或本次内容标题
    :param content: 正文内容，纯文本，支持换行
    :param as_sub_doc: 是否创建为子文档（新页面）；用户说「创建子文档」「新建子页面」时传 True
    """
    result = await feishu_service.create_document(title, content, as_sub_doc=as_sub_doc)
    if result.get("success"):
        url = result.get("url", "")
        msg = f"已写入飞书文档：{url}"
        if result.get("warning"):
            msg += f"（{result['warning']}）"
        return msg
    return f"写入失败：{result.get('error', '未知错误')}"
