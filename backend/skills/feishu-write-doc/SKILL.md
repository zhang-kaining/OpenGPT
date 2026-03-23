---
name: feishu-write-doc
description: 将内容写入飞书文档（知识库页或云空间）
enabled: true
requires_env: [FEISHU_APP_ID, FEISHU_APP_SECRET]
---

当用户说「写文档到飞书」「保存到飞书文档」「写到 wiki」「追加到知识库」等时，调用 **feishu_write_doc** 工具。
当用户说「创建子文档」「新建子页面」「在下面建一个子页」等时，调用时传 **as_sub_doc=true**，会在当前配置的 Wiki 节点下新建一个子页面并写入内容。

**配置说明**（在 `.env` 中至少配置其一）：
- **FEISHU_WIKI_NODE_TOKEN**：知识库页面 token（浏览器打开 Wiki 页，URL 里 `/wiki/` 后面的那串）。配置后：默认**追加**到该页末尾；若 as_sub_doc=true 则在该页下**创建子文档**（新页面）。
- **FEISHU_DEFAULT_FOLDER_TOKEN**：云空间文件夹 token。配置后会在该文件夹下**新建**一篇 docx 并写入内容。
- 若两者都未配置，将尝试在应用默认空间根目录创建文档（可能因权限失败）。

工具参数：
- **title**（必填）：文档标题或本次内容的标题。
- **content**（必填）：正文内容，纯文本，支持换行。
- **as_sub_doc**（可选，默认 false）：为 true 时在 Wiki 下创建子文档（新页面），而非追加到当前页。

写入成功后告知用户文档链接或「已创建子文档」即可。