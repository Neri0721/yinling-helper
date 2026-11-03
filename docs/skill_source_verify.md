# Skill 接入说明 · source_verify

> 银龄核查助手 / 任务一。服务文件：`skill_source_verify.py`，默认端口 **8792**。

## 1. 做什么，不做什么

**做**：判断 URL 是否属于权威来源白名单；对官方/央媒页面抓正文并摘 300 字。

**不做**：不判断页面内容真假、不做截图鉴伪；非白名单来源不抓正文，只标等级。

复用 `server.py` 的 `whitelisted()` / `source_tier()` / `page_text()` / `_source_name()` / `_media_name()`，不复制判级逻辑。

## 2. 启动

```bash
python skill_source_verify.py        # 默认 8792
python skill_source_verify.py 9001
```

## 3. 接口

### GET /health

```json
{"ok": true, "whitelist": 10, "media": 6, "timeout_ms": 20000}
```

### POST /source_verify

请求：

```json
{"url": "https://www.piyao.org.cn/20260911/4109d92150f94fd6be856f05d7ce8042/c.html"}
```

响应：

```json
{
  "official": true,
  "tier": "official",
  "source_name": "中国互联网联合辟谣平台",
  "excerpt": "……正文前 300 字……",
  "source_type": "official",
  "error": null
}
```

| 字段 | 说明 |
|---|---|
| `official` | 仅由白名单域名决定，与抓取是否成功无关 |
| `tier` | 三值：`official` / `media` / `dataset`；非官方非央媒统一归 `dataset`（只能作线索） |
| `source_type` | 原始判断：`official` / `media` / `web` / `unknown`，用于区分“dataset 里的普通网页” |
| `source_name` | 官方站点名 / 央媒名 / 域名 |
| `excerpt` | 抓取成功时前 3 行、最多 300 字；未抓取或失败为空 |
| `error` | `null` / `not_authoritative` / `fetch_failed` / `dns_failed` / `private_address` / `invalid_scheme` |

## 4. 错误码

| HTTP | 场景 | 响应 |
|---|---|---|
| 400 | JSON 解析失败 | `{"error":"bad json"}` |
| 400 | `url` 为空 | `{"error":"empty url"}` |
| 400 | 超过 2048 字 | `{"error":"url too long"}` |
| 400 | 非 http/https | `{"error":"invalid url scheme"}` |
| 404 | 路径不是 `/source_verify` | `{"error":"not found"}` |
| 413 | 请求体超过 1 MB | `{"error":"payload too large"}` |

> 抓取失败不是 5xx：仍返回 200，`official` 按域名判定，`excerpt` 为空，`error` 说明原因。

## 5. 超时与安全

- 单次抓取 `page_text()` 超时 15 秒；服务侧建议平台超时设 **20 秒**。
- 只抓 `official` / `media` 页面；其他来源不发起请求。
- 抓取前解析域名，拒绝回环、内网、链路本地、保留地址（防 SSRF）；DNS 解析失败不抓取。
- 不落盘、不写正文到日志。

## 6. 自测

```bash
python skill_source_verify.py
curl -s http://127.0.0.1:8792/health
curl -s -X POST http://127.0.0.1:8792/source_verify \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.piyao.org.cn/20260911/4109d92150f94fd6be856f05d7ce8042/c.html"}'
```

断网时 `excerpt` 为空、`error` 为 `fetch_failed` 或 `dns_failed`，`official` 仍为 `true`——来源等级与能否抓到正文分开。