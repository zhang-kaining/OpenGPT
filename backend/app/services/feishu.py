import re
import json
import asyncio
import logging
import httpx
from app.config import get_settings

logger = logging.getLogger(__name__)


async def _request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    max_retries: int = 3,
    **kwargs,
) -> httpx.Response:
    """发送 HTTP 请求，遇 429 自动重试（指数退避）。"""
    for attempt in range(max_retries + 1):
        resp = await getattr(client, method)(url, **kwargs)
        if resp.status_code != 429:
            return resp
        wait = min(1.0 * (2 ** attempt), 10.0)
        logger.warning("飞书 429 限流, %s 秒后重试 (%d/%d): %s", wait, attempt + 1, max_retries, url)
        await asyncio.sleep(wait)
    return resp

# 飞书 docx block_type
BLOCK_TYPE_TEXT = 2
BLOCK_TYPE_HEADING1 = 3
BLOCK_TYPE_HEADING2 = 4
BLOCK_TYPE_HEADING3 = 5
BLOCK_TYPE_HEADING4 = 6
BLOCK_TYPE_HEADING5 = 7
BLOCK_TYPE_HEADING6 = 8
BLOCK_TYPE_HEADING7 = 9
BLOCK_TYPE_BULLET = 12
BLOCK_TYPE_ORDERED = 13
BLOCK_TYPE_TABLE = 31

# Markdown 标题前缀 -> block_type（长的优先匹配）
_HEADING_BLOCK_TYPES = {
    "######": BLOCK_TYPE_HEADING6,
    "#####": BLOCK_TYPE_HEADING5,
    "####": BLOCK_TYPE_HEADING4,
    "###": BLOCK_TYPE_HEADING3,
    "##": BLOCK_TYPE_HEADING2,
    "#": BLOCK_TYPE_HEADING1,
}

# block_type -> 对应的 JSON 字段名
_BLOCK_FIELD_MAP = {
    BLOCK_TYPE_TEXT: "text",
    BLOCK_TYPE_HEADING1: "heading1", BLOCK_TYPE_HEADING2: "heading2",
    BLOCK_TYPE_HEADING3: "heading3", BLOCK_TYPE_HEADING4: "heading4",
    BLOCK_TYPE_HEADING5: "heading5", BLOCK_TYPE_HEADING6: "heading6",
    BLOCK_TYPE_HEADING7: "heading7",
    BLOCK_TYPE_BULLET: "bullet",
    BLOCK_TYPE_ORDERED: "ordered",
}

_RE_ORDERED = re.compile(r"^(\d+)[.)]\s+(.*)")
_RE_BULLET = re.compile(r"^[-*+]\s+(.*)")
_RE_MD_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
_RE_INLINE_CODE = re.compile(r"`([^`]+)`")
_RE_EMPHASIS = re.compile(r"(\*\*|__|\*|_|~~)")
_RE_FENCED_CODE_BLOCK = re.compile(r"```[\s\S]*?```")


def _strip_inline_markdown(text: str) -> str:
    cleaned = text or ""
    cleaned = _RE_INLINE_CODE.sub(r"\1", cleaned)
    cleaned = _RE_EMPHASIS.sub("", cleaned)
    return cleaned.strip()


def _normalize_inline_text(text: str) -> str:
    cleaned = text or ""
    cleaned = _RE_INLINE_CODE.sub(r"\1", cleaned)
    cleaned = _RE_EMPHASIS.sub("", cleaned)
    return cleaned


def _make_post_text(text: str) -> dict:
    return {"tag": "text", "text": text or " "}


def _extract_message_title(content: str, default_title: str = "OpenGPT") -> str:
    for raw_line in (content or "").splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("# "):
            return (_strip_inline_markdown(stripped[2:]) or default_title)[:60]
        if stripped.startswith("## "):
            return (_strip_inline_markdown(stripped[3:]) or default_title)[:60]
        if stripped.startswith("### "):
            return (_strip_inline_markdown(stripped[4:]) or default_title)[:60]
    return default_title


def _parse_post_inline_elements(text: str) -> list[dict]:
    elements: list[dict] = []
    cursor = 0
    raw = text or ""
    for match in _RE_MD_LINK.finditer(raw):
        start, end = match.span()
        if start > cursor:
            prefix = _normalize_inline_text(raw[cursor:start])
            if prefix:
                elements.append(_make_post_text(prefix))
        label = _strip_inline_markdown(match.group(1))
        href = match.group(2).strip()
        if label and href:
            elements.append({"tag": "a", "text": label, "href": href})
        cursor = end
    if cursor < len(raw):
        suffix = _normalize_inline_text(raw[cursor:])
        if suffix:
            elements.append(_make_post_text(suffix))
    return elements or [_make_post_text(_strip_inline_markdown(raw) or " ")]


def _markdown_to_post_content(content: str, default_title: str = "OpenGPT") -> str:
    lines = (content or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    title = default_title
    body: list[list[dict]] = []
    in_code_block = False

    for raw_line in lines:
        stripped = raw_line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            body.append([_make_post_text(f"    {_strip_inline_markdown(raw_line) or ' '}")])
            continue
        if not stripped:
            continue
        if stripped.startswith("# "):
            heading = _strip_inline_markdown(stripped[2:].strip()) or default_title
            if title == default_title:
                title = heading[:60]
                continue
            body.append([_make_post_text(f"【{heading}】")])
            continue
        if stripped.startswith("## "):
            heading = _strip_inline_markdown(stripped[3:].strip()) or " "
            body.append([_make_post_text(f"【{heading}】")])
            continue
        if stripped.startswith("### "):
            heading = _strip_inline_markdown(stripped[4:].strip()) or " "
            body.append([_make_post_text(f"【{heading}】")])
            continue

        ordered = _RE_ORDERED.match(stripped)
        if ordered:
            body.append(_parse_post_inline_elements(f"{ordered.group(1)}. {ordered.group(2).strip()}"))
            continue

        bullet = _RE_BULLET.match(stripped)
        if bullet:
            body.append(_parse_post_inline_elements(f"• {bullet.group(1).strip()}"))
            continue

        if stripped.startswith(">"):
            quote = _strip_inline_markdown(stripped.lstrip(">").strip()) or " "
            body.append([_make_post_text(f"引用：{quote}")])
            continue

        body.append(_parse_post_inline_elements(stripped))

    payload = {
        "zh_cn": {
            "title": title[:60] or default_title,
            "content": body or [[_make_post_text(_strip_inline_markdown(content) or " ")]],
        }
    }
    return json.dumps(payload, ensure_ascii=False)


def _markdown_to_interactive_content(content: str, default_title: str = "OpenGPT") -> str:
    title = _extract_message_title(content, default_title=default_title)
    normalized = (content or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    body = normalized or " "
    first_line, _, rest = body.partition("\n")
    if first_line.strip().startswith(("# ", "## ", "### ")) and rest.strip():
        body = rest.strip()

    payload = {
        "config": {
            "wide_screen_mode": True,
            "enable_forward": True,
        },
        "header": {
            "template": "blue",
            "title": {
                "tag": "plain_text",
                "content": title,
            },
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": body,
                },
            }
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


def _classify_line(line: str) -> tuple[int, str]:
    """将一行 Markdown 文本分类为飞书 block_type 和纯文本内容。"""
    stripped = line.strip()
    # 1. 标题 # / ## / ### ...
    for prefix, btype in _HEADING_BLOCK_TYPES.items():
        if stripped.startswith(prefix + " "):
            return btype, stripped[len(prefix) + 1:].strip() or " "
    # 2. 无序列表 - / * / +
    m = _RE_BULLET.match(stripped)
    if m:
        return BLOCK_TYPE_BULLET, m.group(1).strip() or " "
    # 3. 有序列表 1. / 2) ...
    m = _RE_ORDERED.match(stripped)
    if m:
        return BLOCK_TYPE_ORDERED, m.group(2).strip() or " "
    # 4. 引用 > （飞书没有原生引用块，用无序列表近似表达）
    if stripped.startswith("> ") or stripped.startswith(">"):
        text = stripped.lstrip(">").strip() or " "
        return BLOCK_TYPE_TEXT, f"💬 {text}"
    # 5. 普通文本
    return BLOCK_TYPE_TEXT, stripped or " "

# 不同飞书应用（app_id/app_secret）必须使用各自 token，避免切换配置后误复用旧 token。
_token_cache: dict[str, dict[str, float | str]] = {}


def _wiki_url(node_token: str) -> str:
    """生成可在浏览器打开的 Wiki 页链接（使用租户域名）。"""
    base = (get_settings().feishu_wiki_base_url or "https://open.feishu.cn").rstrip("/")
    return f"{base}/wiki/{node_token}"


def _parse_md_table(lines: list[str]) -> tuple[int, int, list[list[str]]] | None:
    """
    解析 Markdown 表格，返回 (行数, 列数, 单元格二维列表) 或 None。
    支持 | a | b | 和 |-|-| 分隔行。
    """
    if len(lines) < 2:
        return None
    rows: list[list[str]] = []
    for line in lines:
        line = line.strip()
        if not line or not line.startswith("|"):
            return None
        # 去掉首尾 |，按 | 分割，去掉空白
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not cells:
            return None
        # 分隔行：|---|---| 或 |:---|:---:|---:|
        if re.match(r"^[\s\-:]+$", "".join(cells)):
            continue
        rows.append(cells)
    if len(rows) < 1:
        return None
    cols = len(rows[0])
    if not all(len(r) == cols for r in rows):
        return None
    return len(rows), cols, rows


async def get_tenant_access_token() -> str:
    """获取飞书 tenant_access_token，自动缓存"""
    import time
    s = get_settings()
    app_id = (s.feishu_app_id or "").strip()
    app_secret = (s.feishu_app_secret or "").strip()
    cache_key = f"{app_id}::{app_secret}"
    cached = _token_cache.get(cache_key)
    if cached and cached.get("token") and time.time() < float(cached.get("expires_at", 0)) - 60:
        return str(cached["token"])

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={
                "app_id": app_id,
                "app_secret": app_secret,
            },
            timeout=10,
        )
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"飞书获取 token 失败: {data}")

        _token_cache[cache_key] = {
            "token": data["tenant_access_token"],
            "expires_at": time.time() + data.get("expire", 7200),
        }
        return str(_token_cache[cache_key]["token"])


async def send_message(content: str, receive_id: str | None = None) -> dict:
    """
    发送飞书消息。
    receive_id: 接收者 open_id（ou_xxx）或 chat_id（oc_xxx）。
                不传则使用 .env 里的 FEISHU_DEFAULT_OPEN_ID。
    """
    target_id = receive_id or get_settings().feishu_default_open_id
    if not target_id:
        return {"success": False, "error": "未配置接收者 ID（FEISHU_DEFAULT_OPEN_ID）"}

    # 判断 ID 类型
    if target_id.startswith("oc_"):
        id_type = "chat_id"
    else:
        id_type = "open_id"

    token = await get_tenant_access_token()
    post_content = _markdown_to_post_content(content)
    interactive_content = _markdown_to_interactive_content(content)
    msg_type = "interactive"
    payload_content = interactive_content

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://open.feishu.cn/open-apis/im/v1/messages",
            params={"receive_id_type": id_type},
            headers={"Authorization": f"Bearer {token}"},
            json={
                "receive_id": target_id,
                "msg_type": msg_type,
                "content": payload_content,
            },
            timeout=15,
        )
        data = resp.json()
        if data.get("code") != 0:
            logger.warning("飞书 interactive 发送失败，回退 post: %s", data.get("msg", "未知错误"))
            resp = await client.post(
                "https://open.feishu.cn/open-apis/im/v1/messages",
                params={"receive_id_type": id_type},
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "receive_id": target_id,
                    "msg_type": "post",
                    "content": post_content,
                },
                timeout=15,
            )
            data = resp.json()
            if data.get("code") == 0:
                return {"success": True, "message_id": data.get("data", {}).get("message_id", "")}
            return {"success": False, "error": data.get("msg", "未知错误")}
        return {"success": True, "message_id": data.get("data", {}).get("message_id", "")}


async def _create_table_and_fill(
    client: httpx.AsyncClient,
    access_token: str,
    document_id: str,
    row_size: int,
    column_size: int,
    cells: list[list[str]],
) -> str | None:
    """创建表格块并填充单元格内容。返回 None 成功，否则错误信息。"""
    url_base = f"https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks"
    # 1. 创建空表格（block_type 31）
    resp = await _request_with_retry(
        client, "post",
        f"{url_base}/{document_id}/children",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "children": [
                {
                    "block_type": BLOCK_TYPE_TABLE,
                    "table": {
                        "property": {
                            "row_size": row_size,
                            "column_size": column_size,
                            "header_row": True,
                        }
                    },
                }
            ],
            "index": -1,
        },
        timeout=15,
    )
    try:
        data = resp.json() if resp.text else {}
    except Exception:
        return f"创建表格接口返回非 JSON: {resp.status_code} {resp.text[:200]}"
    if data.get("code", 0) != 0:
        return data.get("msg", str(data))
    # 2. 从响应直接拿 table 块信息，cell_ids 在 table.cells 里
    resp_items = data.get("data", {}).get("children") or []
    if not resp_items:
        return "创建表格未返回 block 数据"
    table_block = resp_items[0]
    table_block_id = table_block.get("block_id")
    # 优先读 table.cells（飞书实际响应字段）
    cell_ids: list[str] = table_block.get("table", {}).get("cells") or table_block.get("children") or []
    if not table_block_id:
        return "创建表格未返回 block_id"
    if len(cell_ids) < row_size * column_size:
        return f"表格单元格数量不足: 期望 {row_size * column_size}，实际 {len(cell_ids)}"
    # 3. 向每个单元格写入文本：取 table_cell 内默认文本块并更新，避免产生多余空行
    flat_cells = [cells[r][c] for r in range(row_size) for c in range(column_size)]
    for idx, cell_text in enumerate(flat_cells):
        if idx >= len(cell_ids):
            break
        cell_id = cell_ids[idx]

        # 取该 table_cell 下的第一个文本块（创建时自动生成）
        gc = await _request_with_retry(
            client, "get",
            f"{url_base}/{cell_id}/children",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"page_size": 10},
            timeout=10,
        )
        try:
            gd = gc.json() if gc.text else {}
        except Exception:
            gd = {}
        cell_children = gd.get("data", {}).get("items") or []
        text_block_id = cell_children[0].get("block_id") if cell_children else None

        if text_block_id:
            r = await _request_with_retry(
                client, "patch",
                f"{url_base}/{text_block_id}",
                headers={"Authorization": f"Bearer {access_token}"},
                json={
                    "update_text_elements": {
                        "elements": [{"text_run": {"content": cell_text or " "}}]
                    }
                },
                timeout=10,
            )
        else:
            r = await _request_with_retry(
                client, "post",
                f"{url_base}/{cell_id}/children",
                headers={"Authorization": f"Bearer {access_token}"},
                json={
                    "children": [
                        {
                            "block_type": BLOCK_TYPE_TEXT,
                            "text": {"elements": [{"text_run": {"content": cell_text or " "}}]},
                        }
                    ],
                    "index": -1,
                },
                timeout=10,
            )

        if r.status_code == 204:
            continue
        try:
            d = r.json() if r.text else {}
        except Exception:
            return f"写入单元格返回非 JSON: {r.status_code}"
        if d.get("code", 0) != 0:
            return d.get("msg", str(d))
    return None


async def _append_docx_content(
    client: httpx.AsyncClient, access_token: str, document_id: str, content: str, title: str | None = None
) -> str | None:
    """向已存在的 docx 末尾追加段落；若为 Markdown 表格则插入原生表格块。返回 None 表示成功，否则返回错误信息。"""
    logger.info("=== _append_docx_content 开始 ===")
    logger.info("原始 content (%d chars):\n%s", len(content or ""), content)
    lines: list[str] = []
    if title and title.strip():
        lines.append(title.strip())
    lines.extend((content or "").strip().split("\n"))
    if not lines:
        return None
    logger.info("拆分为 %d 行:", len(lines))
    for idx, l in enumerate(lines):
        logger.info("  line[%d]: %r", idx, l)
    i = 0
    while i < len(lines):
        # 尝试从当前行起解析为 Markdown 表格（连续以 | 开头的行）
        chunk: list[str] = []
        j = i
        while j < len(lines) and lines[j].strip().startswith("|"):
            chunk.append(lines[j])
            j += 1
            if len(chunk) > 100:
                break
        parsed = _parse_md_table(chunk) if len(chunk) >= 2 else None
        if chunk:
            logger.info("line[%d] 起找到 %d 行 | 开头, parse 结果: %s",
                         i, len(chunk), f"{parsed[0]}x{parsed[1]}" if parsed else "None")
        if parsed:
            row_size, column_size, cells = parsed
            logger.info("插入表格 %dx%d, 第一行: %s", row_size, column_size, cells[0] if cells else [])
            err = await _create_table_and_fill(
                client, access_token, document_id, row_size, column_size, cells
            )
            if err:
                logger.error("表格创建失败: %s", err)
                return err
            i = j
            continue
        # 跳过空行，减少 API 调用避免触发限流
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        block_type, text_content = _classify_line(line)
        logger.info("line[%d] -> block_type=%d, text=%r", i, block_type, text_content[:80])
        field_name = _BLOCK_FIELD_MAP.get(block_type, "text")
        block_body = {field_name: {"elements": [{"text_run": {"content": text_content}}]}}
        children = [{"block_type": block_type, **block_body}]
        resp = await _request_with_retry(
            client, "post",
            f"https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks/{document_id}/children",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"children": children, "index": -1},
            timeout=15,
        )
        if resp.status_code != 204:
            try:
                data = resp.json() if resp.text else {}
            except Exception:
                return f"追加段落返回非 JSON: {resp.status_code}"
            if data.get("code", 0) != 0:
                return data.get("msg", str(data))
        i += 1
    return None


async def write_to_wiki(content: str, title: str | None = None) -> dict:
    """
    向配置的 Wiki 页面追加内容。使用 FEISHU_WIKI_NODE_TOKEN（知识库 URL 里 /wiki/ 后面的 token）。
    返回 {"success": True, "url": "https://open.feishu.cn/wiki/xxx"} 或 {"success": False, "error": "..."}
    """
    node_token = (get_settings().feishu_wiki_node_token or "").strip()
    if not node_token:
        return {"success": False, "error": "未配置 FEISHU_WIKI_NODE_TOKEN（知识库页面 token）"}

    access_token = await get_tenant_access_token()

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://open.feishu.cn/open-apis/wiki/v2/spaces/get_node",
            params={"token": node_token, "obj_type": "wiki"},
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        data = resp.json()
        if data.get("code") != 0:
            return {"success": False, "error": data.get("msg", str(data))}

        node = data.get("data", {}).get("node", {})
        obj_token = node.get("obj_token")
        obj_type = node.get("obj_type", "")
        if not obj_token:
            return {"success": False, "error": "该 Wiki 节点未关联文档"}
        if obj_type not in ("docx", "doc"):
            return {"success": False, "error": f"该节点类型为 {obj_type}，仅支持 docx 文档页"}

        err = await _append_docx_content(client, access_token, obj_token, content, title=title)
        if err:
            return {"success": False, "error": f"写入内容失败：{err}"}

    return {"success": True, "url": _wiki_url(node_token)}


async def create_wiki_sub_doc(
    client: httpx.AsyncClient,
    access_token: str,
    space_id: str,
    parent_node_token: str,
    title: str,
    content: str,
) -> dict:
    """
    在知识库指定父节点下创建子文档（新页面）并写入内容。
    返回 {"success": True, "url": "https://open.feishu.cn/wiki/{new_node_token}"} 或 {"success": False, "error": "..."}
    """
    resp = await client.post(
        f"https://open.feishu.cn/open-apis/wiki/v2/spaces/{space_id}/nodes",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "obj_type": "docx",
            "node_type": "origin",
            "parent_node_token": parent_node_token,
            "title": (title or "未命名")[:800],
        },
        timeout=15,
    )
    data = resp.json()
    if data.get("code") != 0:
        return {"success": False, "error": data.get("msg", str(data))}

    node = data.get("data", {}).get("node", {})
    new_node_token = node.get("node_token")
    obj_token = node.get("obj_token")
    if not obj_token:
        return {"success": False, "error": "创建节点未返回 obj_token"}

    err = await _append_docx_content(client, access_token, obj_token, content, title=None)
    if err:
        return {"success": False, "error": f"写入内容失败：{err}"}

    return {"success": True, "url": _wiki_url(new_node_token)}


async def create_document(title: str, content: str, as_sub_doc: bool = False) -> dict:
    """
    写文档到飞书。若配置了 FEISHU_WIKI_NODE_TOKEN：
    - as_sub_doc=False：追加到该 Wiki 页末尾；
    - as_sub_doc=True：在该节点下创建子文档（新页面）并写入内容。
    否则在云空间创建新 docx。
    返回 {"success": True, "url": "..."} 或 {"success": False, "error": "..."}
    """
    logger.info("=== create_document 入口 ===")
    logger.info("title=%r, as_sub_doc=%s, content长度=%d", title, as_sub_doc, len(content or ""))
    logger.info("content前500字:\n%s", (content or "")[:500])
    wiki_token = (get_settings().feishu_wiki_node_token or "").strip()
    if wiki_token:
        if as_sub_doc:
            access_token = await get_tenant_access_token()
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://open.feishu.cn/open-apis/wiki/v2/spaces/get_node",
                    params={"token": wiki_token, "obj_type": "wiki"},
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=10,
                )
                data = resp.json()
                if data.get("code") != 0:
                    return {"success": False, "error": data.get("msg", str(data))}
                node = data.get("data", {}).get("node", {})
                space_id = node.get("space_id")
                if not space_id:
                    return {"success": False, "error": "未获取到知识库 space_id"}
                return await create_wiki_sub_doc(
                    client, access_token, space_id, wiki_token, title or "未命名", content or ""
                )
        return await write_to_wiki(content, title=title)

    token = await get_tenant_access_token()
    folder_token = (get_settings().feishu_default_folder_token or "").strip() or None

    async with httpx.AsyncClient() as client:
        # 1. 创建文档
        create_body: dict = {"title": title[:800] if title else "未命名文档"}
        if folder_token:
            create_body["folder_token"] = folder_token

        resp = await client.post(
            "https://open.feishu.cn/open-apis/docx/v1/documents",
            headers={"Authorization": f"Bearer {token}"},
            json=create_body,
            timeout=15,
        )
        data = resp.json()
        if data.get("code") != 0:
            return {"success": False, "error": data.get("msg", str(data))}

        doc_info = data.get("data", {}).get("document", {})
        document_id = doc_info.get("document_id")
        if not document_id:
            return {"success": False, "error": "创建文档未返回 document_id"}

        doc_url = f"https://open.feishu.cn/docx/{document_id}"

        # 2. 写入正文（按行拆成段落，逐段插入）
        content = (content or "").strip()
        if content:
            lines = content.split("\n")
            # 单次请求插入的 block 不宜过多，每批最多 20 段
            batch_size = 20
            for i in range(0, len(lines), batch_size):
                batch = lines[i : i + batch_size]
                children = [
                    {
                        "block_type": 2,
                        "text": {
                            "elements": [{"text_run": {"content": line or " "}}]
                        },
                    }
                    for line in batch
                ]
                block_resp = await client.post(
                    f"https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks/{document_id}/children",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"children": children, "index": -1},
                    timeout=15,
                )
                block_data = block_resp.json()
                if block_data.get("code") != 0:
                    # 文档已创建，仅写入失败时仍返回成功并带上链接
                    return {
                        "success": True,
                        "document_id": document_id,
                        "url": doc_url,
                        "warning": f"文档已创建，但部分内容写入失败：{block_data.get('msg', '')}",
                    }

        return {"success": True, "document_id": document_id, "url": doc_url}


# ---- Tool 定义（供 azure_openai.py 使用）----

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "feishu_send_message",
        "description": (
            "将内容发送到飞书。当用户说发到飞书、发给我、推送到飞书时使用此工具。"
            "发送内容应为纯文本，可包含换行。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "要发送的消息内容，纯文本格式"
                }
            },
            "required": ["content"]
        }
    }
}

# 写文档已拆到 Skill「feishu-write-doc」，配置 FEISHU_WIKI_NODE_TOKEN 或 FEISHU_DEFAULT_FOLDER_TOKEN 后可用


async def get_app_permissions_info() -> dict:
    """
    调用飞书接口查询当前应用信息及权限相关数据（供排查权限用）。
    返回包含 application/me、contact/scopes、以及一次 wiki 节点与 docx 写入的探测结果。
    """
    token = await get_tenant_access_token()
    out: dict = {"app": None, "contact_scopes": None, "wiki_node": None, "docx_write": None}

    async with httpx.AsyncClient() as client:
        # 1. 应用信息（可能含权限相关）
        r = await client.get(
            "https://open.feishu.cn/open-apis/application/v6/applications/me",
            params={"lang": "zh_cn"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        out["app"] = r.json()

        # 2. 通讯录授权范围
        r2 = await client.get(
            "https://open.feishu.cn/open-apis/contact/v3/scopes",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        out["contact_scopes"] = r2.json()

        # 3. Wiki 节点信息（你配置的 FEISHU_WIKI_NODE_TOKEN）
        node_token = (get_settings().feishu_wiki_node_token or "").strip()
        if node_token:
            r3 = await client.get(
                "https://open.feishu.cn/open-apis/wiki/v2/spaces/get_node",
                params={"token": node_token, "obj_type": "wiki"},
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            out["wiki_node"] = r3.json()
            # 4. 若拿到 obj_token，尝试追加一段文字看是否 403
            data3 = r3.json()
            if data3.get("code") == 0:
                node = data3.get("data", {}).get("node", {})
                obj_token = node.get("obj_token")
                if obj_token:
                    r4 = await client.post(
                        f"https://open.feishu.cn/open-apis/docx/v1/documents/{obj_token}/blocks/{obj_token}/children",
                        headers={"Authorization": f"Bearer {token}"},
                        json={
                            "children": [
                                {"block_type": 2, "text": {"elements": [{"text_run": {"content": "[权限探测]"}}]}}
                            ],
                            "index": -1,
                        },
                        timeout=10,
                    )
                    out["docx_write"] = r4.json()

    return out


async def list_visible_users(limit: int = 200) -> list[dict]:
    """
    拉取当前应用可见用户列表（用于选择默认接收人 OpenID）。
    返回: [{"open_id": "...", "name": "..."}]
    """
    s = get_settings()
    token = await get_tenant_access_token()
    logger.info(
        "feishu list_visible_users start app_id=%s default_open_id=%s limit=%d",
        (s.feishu_app_id or "").strip(),
        (s.feishu_default_open_id or "").strip(),
        limit,
    )
    users: list[dict] = []
    page_token = ""
    page_size = 50

    async with httpx.AsyncClient() as client:
        while len(users) < limit:
            params = {"user_id_type": "open_id", "page_size": page_size}
            if page_token:
                params["page_token"] = page_token
            resp = await client.get(
                "https://open.feishu.cn/open-apis/contact/v3/users",
                params=params,
                headers={"Authorization": f"Bearer {token}"},
                timeout=12,
            )
            data = resp.json()
            if data.get("code") != 0:
                raise RuntimeError(data.get("msg", str(data)))

            items = data.get("data", {}).get("items") or []
            for it in items:
                open_id = str(it.get("open_id") or "").strip()
                if not open_id:
                    continue
                users.append({
                    "open_id": open_id,
                    "name": str(it.get("name") or it.get("en_name") or open_id),
                })
                if len(users) >= limit:
                    break

            has_more = bool(data.get("data", {}).get("has_more"))
            page_token = str(data.get("data", {}).get("page_token") or "").strip()
            if not has_more or not page_token:
                break

    preview = ", ".join(
        f"{u.get('name','')}<{u.get('open_id','')}>"
        for u in users[:3]
    )
    logger.info("feishu list_visible_users done count=%d preview=%s", len(users), preview or "(empty)")
    return users
