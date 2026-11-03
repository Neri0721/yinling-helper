# 给 CodeArts 的任务单

> 交给接手编码的 Agent。先读 `docs/知识库交接说明.md`，再按本单执行。
> 项目根目录：`C:\Users\风又音理233\Desktop\银龄核查助手`
> 截止：2026-11-30（报名与初赛材料）

## 总原则（每次改动都要遵守）

1. **不要引入第三方依赖**。项目至今只用 Python 标准库 + `python-docx`（仅文档生成用），部署环境没有 pip。
2. **不要改数据结构**：`tier` 只能是 `official` / `dataset` / `media`，`server.py` 的判级逻辑依赖这三个值。
3. **不要动 `kb.json` / `kb_elderly.json` 的内容**，那是数据资产；需要改就改生成脚本。
4. **每次改完必须自测**：`python -m py_compile` 三个改动文件，再跑 `python tools/recall_test.py`，结果不能比基线（recall@3 = 20/20）差。
5. **密钥只在服务端**。任何出现在 HTML / JS 里的 AK/SK 都算交付事故。

## 任务 1：三个 Skill 封装（最高优先级）

现有 `skill_ocr.py` 是模板，照它的形态做三个服务。

| Skill | 端口 | 职责 | 输入 → 输出 |
|---|---|---|---|
| `kb_search` | 8791 | 检索知识库 | `{query, domain?, top_k?}` → `{hits:[{id,title,snippet,tier,url,date,score}]}` |
| `source_verify` | 8792 | 判断 URL 是否白名单、摘正文 | `{url}` → `{official:bool, tier, source_name, excerpt}` |
| `scam_rules` | 8793 | 诈骗类型识别 | `{text}` → `{is_scam, types:[], risk, advice}` |

**验收**：
- 三个服务都能 `GET /health` 返回当前状态；
- `POST` 用 curl 能跑通最少一例；
- 各配一个 `docs/skill_*.md`，写清契约（照抄 `docs/拍照核查_接入说明.md` 第 9 节的格式）。

**复用提示**：`kb_search` 的核心可以抽 `tools/recall_test.py` 里的倒排索引，也可以直接读 `tools/out/kb_import_elderly.jsonl` 建内存索引；`source_verify` 复用 `server.py` 的 `whitelisted()` 与 `page_text()`；`scam_rules` 复用并扩展 `DANGER_WORDS`，输出四种类型：冒充公检法 / 保健品会销 / 投资理财 / 补贴退税。

## 任务 2：三个 Agent 的提示词资产

在 `prompts/` 下按 Agent 分文件，每个文件包含：system prompt、2-3 条 few-shot、**输入输出 JSON schema**。

| 文件 | Agent | 输出必须包含 |
|---|---|---|
| `prompts/a1_claim.md` | 意图与主张 | `{intent, claim, domain, need_clarify}` |
| `prompts/a2_verify.md` | 核查 | `{risk_level, verdict, evidence:{tier,url,source_name,date,snippet}}` |
| `prompts/a3_rewrite.md` | 转述 | `{conclusion, explanation, action_advice, voice_script, family_share_text}` |

**硬约束**：`a2_verify.md` 里必须写明「只允许依据 evidence 下结论，evidence 为空时 verdict 必须是 `no_evidence`」。这是产品的地基，别被改写掉。

**验收**：用 `tests/testset_20.csv` 的 20 条问题逐条跑一遍，人工看输出是否符合 schema。

## 任务 3：H5 双入口改造

`mobile.html` 现在是「📷 + 输入框 + 核查」。改成：

- 首屏两个大按钮：**拍张照** / **说句话**；
- 打字收进二级页面（保留，但不占首屏）；
- 结果页语音自动播报（现在是个开关，改成默认开）；
- 首屏资源控制在 200 KB 以内，不引外部字体和图标库。

**验收**：手机竖屏打开，不滚动就能看到两个按钮；断网时给出可读提示而不是白屏。

## 任务 4：后端代理骨架

`server.py` 加 `POST /api/proxy`，把请求转发到 AgentArts 部署的地址：

- 地址与密钥从环境变量读（`AGENT_BASE_URL` / `AGENT_TOKEN`），**不写死在代码里**；
- 转发超时 8 秒，超时返回 `{type:"timeout"}` 而不是 500；
- 保留现有 `/api/check` 不动，作为本地降级通道。

**验收**：环境变量不设时，`/api/proxy` 返回明确的「未配置」提示；设了之后能把一次请求转发出去并原样透传响应。

## 任务 5：一键自测

新建 `tools/selftest.py`，一条命令跑完：

1. `py_compile` 所有 `.py`；
2. 起服务 → `/api/health`、`/api/check`（文字一条、图片一条）→ 关服务；
3. `recall_test.py`，打印 recall@1/3/5；
4. 输出 PASS/FAIL 汇总。

**验收**：全绿才算这一轮改完。

## 不要做的事

- 不要把 `kb.json` 全量导入（用 `kb_elderly.json`，理由见交接说明）
- 不要在前端调平台接口
- 不要改 `tests/testset_20.csv` 的 `answer_*` 列（那是标准答案，只允许填 `query_final`）
- 不要为了"效果好看"放宽判级阈值——宁可回答查不到
- 不要重写 `mobile.html` 的视觉风格，老人已经适应的东西别动

## 交付时附一句话

每个任务做完，写一句：**做了什么、验收怎么跑、还剩什么**。不要只贴代码。
