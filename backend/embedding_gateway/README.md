# Embedding Gateway

轻量 OpenAI 兼容 Embeddings 网关。

## 目标

- 对外提供标准 `POST /v1/embeddings`
- 对内转发到 DashScope 多模态向量接口
- 支持纯文本输入（后续可扩展图文/视频）

## 目录

- `main.py`：网关入口与协议转换

## 运行

`start.sh` 已自动拉起网关，默认端口 `8101`。

健康检查：

```bash
curl http://127.0.0.1:8101/health
```

OpenAI 兼容调用示例：

```bash
curl http://127.0.0.1:8101/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"model":"tongyi-embedding-vision-plus","input":"你好"}'
```

