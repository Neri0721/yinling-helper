# Skill 接入说明 · kb_search

> 银龄核查助手 / 任务一。给 AgentArts 包装成插件或 MCP 工具用。
> 服务文件：`skill_kb_search.py`，默认端口 **8791**。

## 1. 做什么，不做什么

**做**：在银龄子集（`tools/out/kb_import_elderly.jsonl`，3,188 块）里做字符二元组 + IDF 检索，返回可追溯的条目。

**不做**：不判断真假、不生成结论、不补写正文。检索不到就是空列表，不返回兜底条目。

## 2. 启动

```bash
python tools/prep_kb.py kb_elderly.json     # 首次或数据更新后，生成导入包
python skill_kb_search.py                   # 默认 8791
python skill_kb_search.py 9001              # 自定义端口
```

数据文件缺失时服务仍能启动，但 `GET /health` 返回 `ok=false`，`POST` 返回 503——不静默返回空结果。

## 3. 接口

### GET /health

```json
{"ok": true, "docs": 3188, "terms": 53517, "source": "kb_import_elderly.jsonl", "index_ms": 980, "error": null}
```

### POST /kb_search

请求：

```json
{"query": "喝骨头汤能补钙是真的吗", "domain": "健康", "top_k": 5}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `query` | string | 是 | 待核查说法，最长 200 字 |
| `domain` | string | 否 | `健康` / `钱财` / `政策` / `儿童` / `其他`；不传不过滤 |
| `top_k` | int | 否 | 默认 5，范围 1–20 |

响应：

```json
{
  "hits": [
    {
      "id": "f0bc9f040181-c1",
      "title": "秋天来了，手机里那些“换季谣言”又来了",
      "snippet": "……",
      "tier": "official",
      "url": "https://www.piyao.org.cn/...",
      "date": "2026-09",
      "score": 42.117
    }
  ],
  "query": "喝骨头汤能补钙是真的吗",
  "domain": "健康",
  "top_k": 5,
  "total": 1,
  "ms": 3
}
```

- `tier` 严格三值：`official` / `dataset` / `media`。
- `score` 是字符二元组 IDF 加权和，**只用于排序，不是概率**，不要跨查询比较。
- `snippet` 截 80 字，只用于展示；引用时以 `url` 原文为准。

## 4. 错误码

| HTTP | 场景 | 响应 |
|---|---|---|
| 400 | JSON 解析失败 / 非对象 | `{"error":"bad json"}` |
| 400 | `query` 为空 | `{"error":"empty query"}` |
| 400 | `query` 超过 200 字 | `{"error":"query too long..."}` |
| 400 | `top_k` 非整数或越界 | `{"error":"top_k must be 1-20"}` |
| 404 | 路径不是 `/kb_search` | `{"error":"not found"}` |
| 413 | 请求体超过 1 MB | `{"error":"payload too large"}` |
| 503 | 索引文件缺失/为空 | `{"error":"index unavailable","detail":"..."}` |

## 5. 超时与资源

- 服务端单次检索目标 **< 3 秒**（3,188 块实测个位数毫秒）；建议平台侧超时设 **5 秒**。
- 索引在启动时一次性建好，内存约几十 MB；查询只读，支持并发。
- 不落盘、不写请求正文到日志。

## 6. 自测

```bash
python skill_kb_search.py
curl -s http://127.0.0.1:8791/health
curl -s -X POST http://127.0.0.1:8791/kb_search \
  -H "Content-Type: application/json" \
  -d '{"query":"喝骨头汤能补钙是真的吗","domain":"健康","top_k":3}'
```