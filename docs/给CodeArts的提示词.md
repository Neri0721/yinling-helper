# 给 CodeArts 的完整提示词（整段复制粘贴）

```text
你是这个项目的编码 Agent。项目叫「银龄核查助手」，是一个面向老年人谣言与诈骗核查的
多智能体应用，最终要部署在华为云 AgentArts 上参加第十一届华为 ICT 大赛创新赛（赛题二）。

工作目录：C:\Users\风又音理233\Desktop\银龄核查助手

开始动手之前，先读这两个文件，不要跳过：
1. docs/知识库交接说明.md   —— 数据是什么、字段什么意思、哪里不能碰
2. docs/给CodeArts的任务单.md —— 五个任务和验收标准

读完先回我一句：你理解了哪些约束、打算按什么顺序做。确认后再动代码。

────────────────────────────
【项目现状，帮你建立上下文】
- server.py：单文件 HTTP 服务，文字核查链路已跑通，能返回风险等级/结论/证据/行动建议
- ocr.py / skill_ocr.py：拍照转文字，已支持华为云 OCR、tesseract、mock 三种模式
- kb.json（20,122 条源数据）、kb_elderly.json（银龄子集 3,288 条）
- tools/：知识库生成、测试集、召回评估，六个脚本
- mobile.html：手机版页面，目前是「拍照 + 输入框 + 核查」
- 已有 20 条召回测试集 tests/testset_20.csv，基线 recall@3 = 20/20

────────────────────────────
【硬性约束，违反任何一条都算失败】
1. 只用 Python 标准库。不引入 requests、flask、numpy 等任何第三方包，部署环境没有 pip。
2. 不改数据结构。tier 只能是 official / dataset / media 三个值，server.py 的判级逻辑依赖它。
3. 不改 kb.json / kb_elderly.json 的内容。那是数据资产，要改就改 tools/ 里的生成脚本。
4. 密钥只放服务端。任何出现在 HTML、JS、前端配置里的 AK/SK 都算交付事故。
5. 不放宽判级阈值。宁可返回「查不到」，也不许为了演示好看而降低证据要求。
6. 不重做视觉风格。老人已经适应的界面元素不要动，只做加法。

────────────────────────────
【任务一：三个 Skill 服务】优先级最高
照 skill_ocr.py 的形态（标准库 http.server、GET /health、POST 主接口、独立端口），做三个：

  8791 kb_search      输入 {query, domain?, top_k?}
                      输出 {hits:[{id,title,snippet,tier,url,date,score}]}
  8792 source_verify  输入 {url}
                      输出 {official, tier, source_name, excerpt}
  8793 scam_rules     输入 {text}
                      输出 {is_scam, types, risk, advice}

实现提示：
- kb_search 的索引可参考 tools/recall_test.py 的倒排索引写法，数据读 tools/out/kb_import_elderly.jsonl
- source_verify 复用 server.py 里的 whitelisted() 与 page_text()
- scam_rules 复用并扩展 DANGER_WORDS，输出四种类型：冒充公检法 / 保健品会销 / 投资理财 / 补贴退税
- 三个服务各配一份 docs/skill_<name>.md，写清入参出参、错误码、超时

验收：三个服务 GET /health 都通；POST 用一条真实数据能返回结果；文档齐全。

────────────────────────────
【任务二：三个 Agent 的提示词资产】
在 prompts/ 下建三个文件，每个包含 system prompt、2-3 条 few-shot、输入输出 JSON schema：

  prompts/a1_claim.md    意图与主张  输出 {intent, claim, domain, need_clarify}
  prompts/a2_verify.md   核查        输出 {risk_level, verdict, evidence:{tier,url,source_name,date,snippet}}
  prompts/a3_rewrite.md  转述        输出 {conclusion, explanation, action_advice, voice_script, family_share_text}

a2_verify.md 里必须写死这条：只允许依据 evidence 下结论，evidence 为空时 verdict 必须是 no_evidence。
这是整个产品的地基，不允许被改写或"优化"掉。

验收：用 tests/testset_20.csv 的 20 条问题逐条跑，输出符合 schema。

────────────────────────────
【任务三：手机页双入口改造】
改 mobile.html：首屏放两个大按钮「拍张照」「说句话」，打字收进二级页面；
结果页语音播报改成默认开启；首屏资源控制在 200 KB 内，不引外部字体和图标库。

验收：手机竖屏不滚动就能看到两个按钮；断网时有可读提示，不能白屏。

────────────────────────────
【任务四：后端代理骨架】
server.py 增加 POST /api/proxy，转发到 AgentArts 部署地址：
- 地址和 token 从环境变量 AGENT_BASE_URL / AGENT_TOKEN 读，不写死
- 转发超时 8 秒，超时返回 {"type":"timeout"}，不要抛 500
- 保留现有 /api/check 不动，它作为本地降级通道

验收：不设环境变量时返回明确的「未配置」提示；设了之后能透传一次真实请求。

────────────────────────────
【任务五：一键自测】
新建 tools/selftest.py，一条命令完成：
1) py_compile 所有 .py 文件
2) 起服务 → 请求 /api/health、/api/check（文字一条、图片一条）→ 关服务
3) 跑 tools/recall_test.py，打印 recall@1/3/5
4) 输出 PASS / FAIL 汇总

验收：全绿。以后每轮改动都跑它。

────────────────────────────
【纪律】
- 每完成一个任务，先自测，再汇报。汇报格式固定三行：
    做了什么：____
    怎么验收：____（给命令）
    还剩什么：____
- 不要贴大段代码当汇报，我只看结论和命令。
- 拿不准的时候停下来问我，不要替我做产品决策（尤其是"要不要放宽阈值""要不要删 no_evidence 分支"这类）。
- 修改前先说明打算改哪几个文件，改完说明实际改了哪些。

────────────────────────────
【明确不要做】
- 不要把 kb.json 全量导入（用 kb_elderly.json）
- 不要在前端调平台接口
- 不要改 tests/testset_20.csv 里的 answer_* 列
- 不要为了"效果好看"虚构任何数字或指标
- 不要重写 README 或删除现有脚本

从任务一开始。先读那两个文档，然后告诉我你的计划。
```
