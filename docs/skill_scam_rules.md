# Skill 接入说明 · scam_rules

> 银龄核查助手 / 任务一。服务文件：`skill_scam_rules.py`，默认端口 **8793**。

## 1. 做什么，不做什么

**做**：用规则识别四类老人高频诈骗话术——冒充公检法 / 保健品会销 / 投资理财 / 补贴退税。

**不做**：不下最终真假结论。`is_scam=true` 只表示"命中典型话术"，不是"已核实为骗局"；未命中也可能是新骗法。

复用 `server.py` 的 `DANGER_WORDS`；四类词表在本服务内维护，不改主服务常量。

## 2. 启动

```bash
python skill_scam_rules.py           # 默认 8793
python skill_scam_rules.py 9001
```

## 3. 接口

### GET /health

```json
{"ok": true, "types": 4, "danger_words": 24}
```

### POST /scam_rules

请求：

```json
{"text": "有人打电话说我的账户涉嫌洗钱，要把钱转到安全账户，还要了验证码"}
```

响应：

```json
{
  "is_scam": true,
  "types": ["冒充公检法"],
  "risk": "高风险",
  "advice": "立即挂断，公检法不会电话办案、不会要验证码，也不会让你转到“安全账户”；拨打 96110 核实。"
}
```

| 字段 | 说明 |
|---|---|
| `is_scam` | 是否命中至少一类典型话术 |
| `types` | 命中类型数组，枚举四类；可同时命中多类 |
| `risk` | `高风险` / `中风险` / `低风险` |
| `advice` | 按命中类型拼接的可执行建议；未命中给通用提醒 |

判定规则（可评审）：

- 每类有强信号词与弱信号词：强信号命中 1 个即计入；弱信号需命中 2 个，降低误报。
- 命中 ≥2 类，或命中 1 类且同时命中 `DANGER_WORDS` → `高风险`；命中 1 类 → `中风险`；未命中 → `低风险`。

## 4. 错误码

| HTTP | 场景 | 响应 |
|---|---|---|
| 400 | JSON 解析失败 | `{"error":"bad json"}` |
| 400 | `text` 为空 | `{"error":"empty text"}` |
| 400 | 超过 2000 字 | `{"error":"text too long..."}` |
| 404 | 路径不是 `/scam_rules` | `{"error":"not found"}` |
| 413 | 请求体超过 1 MB | `{"error":"payload too large"}` |

## 5. 超时与资源

- 纯内存字符串匹配，单次目标 **< 500 毫秒**；平台侧建议超时设 **2 秒**。
- 无外网调用、无状态、不落盘。

## 6. 自测

```bash
python skill_scam_rules.py
curl -s http://127.0.0.1:8793/health
curl -s -X POST http://127.0.0.1:8793/scam_rules \
  -H "Content-Type: application/json" \
  -d '{"text":"有人打电话说我的账户涉嫌洗钱，要把钱转到安全账户，还要了验证码"}'
```