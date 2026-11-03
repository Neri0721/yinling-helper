# -*- coding: utf-8 -*-
import os
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

OUT = r"C:\Users\风又音理233\Desktop\银龄核查助手\docs"
DOCX = os.path.join(OUT, "银龄核查助手_作品设计方案_V1.0.docx")
PNG = os.path.join(OUT, "银龄核查_Agent编排图.png")

doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21), Cm(29.7)
sec.top_margin = sec.bottom_margin = Cm(2.4)
sec.left_margin = sec.right_margin = Cm(2.5)


def setrun(r, name):
    r.font.name = name
    r._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), name)


st = doc.styles["Normal"]
st.font.name = "宋体"
st.font.size = Pt(10.5)
st.element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "宋体")


def para(text, indent=True, size=10.5, bold=False, align=None, space=6, color=None, name="宋体"):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.line_spacing = 1.5
    pf.space_after = Pt(space)
    if indent:
        pf.first_line_indent = Pt(21)
    if align is not None:
        p.alignment = align
    r = p.add_run(text)
    r.font.size = Pt(size)
    r.bold = bold
    setrun(r, name)
    if color:
        r.font.color.rgb = RGBColor.from_string(color)
    return p


def h1(text):
    p = doc.add_heading(level=1)
    r = p.add_run(text)
    r.font.size = Pt(16)
    r.font.color.rgb = RGBColor.from_string("B3121D")
    setrun(r, "微软雅黑")
    p.paragraph_format.space_before = Pt(16)
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.keep_with_next = True
    return p


def h2(text):
    p = doc.add_heading(level=2)
    r = p.add_run(text)
    r.font.size = Pt(12.5)
    r.font.color.rgb = RGBColor.from_string("1F2937")
    setrun(r, "微软雅黑")
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    return p


def bullet(text):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.line_spacing = 1.45
    p.paragraph_format.space_after = Pt(3)
    r = p.add_run(text)
    r.font.size = Pt(10.5)
    setrun(r, "宋体")
    return p


def shade(cell, hexc):
    tcPr = cell._tc.get_or_add_tcPr()
    sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear")
    sh.set(qn("w:color"), "auto")
    sh.set(qn("w:fill"), hexc)
    tcPr.append(sh)


def caption(text, before=False):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(8 if before else 4)
    p.paragraph_format.space_after = Pt(4 if before else 12)
    p.paragraph_format.keep_with_next = before
    r = p.add_run(text)
    r.font.size = Pt(9)
    r.font.color.rgb = RGBColor.from_string("6B7280")
    setrun(r, "微软雅黑")
    return p


def tbl(cap, headers, rows, widths, size=9):
    caption(cap, before=True)
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    for i, hd in enumerate(headers):
        c = t.rows[0].cells[i]
        c.text = ""
        p = c.paragraphs[0]
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(hd)
        r.bold = True
        r.font.size = Pt(size)
        setrun(r, "微软雅黑")
        shade(c, "F2F2F2")
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            p = cells[i].paragraphs[0]
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.line_spacing = 1.15
            r = p.add_run(str(v))
            r.font.size = Pt(size)
            setrun(r, "宋体")
    for row in t.rows:
        row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
        for i, wd in enumerate(widths):
            row.cells[i].width = Cm(wd)
    sp = doc.add_paragraph()
    sp.paragraph_format.space_after = Pt(0)
    sp.paragraph_format.line_spacing = 0.6
    return t


# ---------------- 封面 ----------------
for _ in range(5):
    doc.add_paragraph()
para("第十一届华为 ICT 大赛 · 创新赛", indent=False, size=13, align=WD_ALIGN_PARAGRAPH.CENTER, color="6B7280", name="微软雅黑", space=4)
para("赛题二：基于华为云 AgentArts 智能体开发平台打造 Agent", indent=False, size=12.5, align=WD_ALIGN_PARAGRAPH.CENTER, color="6B7280", name="微软雅黑", space=28)
para("银龄核查助手", indent=False, size=34, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, name="微软雅黑", space=6)
para("给子女和社区用的反谣反诈核查智能体", indent=False, size=16, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, name="微软雅黑", space=30)
para("作品设计方案", indent=False, size=15, align=WD_ALIGN_PARAGRAPH.CENTER, color="B3121D", name="微软雅黑", space=60)
for line in ["参赛院校：成都东软学院 计算机与软件学院",
             "团队成员：________　________　________",
             "指导教师：________",
             "版本：V1.0　　日期：2026 年 11 月"]:
    para(line, indent=False, size=11, align=WD_ALIGN_PARAGRAPH.CENTER, space=8, name="微软雅黑")
doc.add_page_break()

# ---------------- 一 ----------------
h1("一、项目定位")
h2("1.1 一句话说明")
para("「银龄核查助手」是一个部署在华为云 AgentArts 上的多智能体应用：子女或社区网格员把长辈收到的一条可疑消息转发进来（文字、截图或语音），系统在数秒内给出风险等级、结论、可追溯的权威出处，以及一句能让老人听懂并照做的转述。")
para("它的核心不是「又一个问答机器人」，而是三件事：结论必须有出处、查不到就明说、说人话。")

h2("1.2 我们服务的其实是两个人")
para("这是本项目与多数同类作品最不同的地方：发起核查的人和接收结论的人，不是同一个。")
para("发起者是子女和社区网格员——他们有能力判断「这条可疑」，也有动力去查；接收者是老人——他只关心「能不能信、要不要做」。把这两个人混为一谈，产品就会做成「让老人自己打开网页输入一句话」，而这恰恰是老人不会做的事。")
tbl("表 1  两类用户与三个端的真实分工",
    ["端", "谁在用", "用来做什么", "为什么是它"],
    [["手机 H5（微信内打开）", "子女、老人", "拍照 / 说话 / 贴文字，看结论，转发", "老人不装 App，微信是唯一稳定的入口"],
     ["语音播报", "老人", "听结论，不用看字", "老花、白内障人群的刚需"],
     ["电脑端页面", "社区网格员", "批量核查、生成群公告", "他们坐在电脑前办公，需要一次处理多条"]],
    [3.2, 3.0, 5.0, 4.8])
para("所以形态问题不是「手机还是电脑」，而是「三个端各有各的人」。这条要在答辩时主动讲，否则评委的第一个问题就是：老人凭什么会打开你的网页。")

h2("1.3 为什么定位为行业赋能型")
para("赛题二给了四个方向。我们选择行业赋能型（基层治理与社区养老），而非常见的生活服务型，理由很直白：")
bullet("生活服务型的付费方是老人，而老人不会为核查付费，这个模型讲不通。")
bullet("基层治理与养老服务机构有预算、有采购流程、有政策依据（反诈宣传、适老化改造、老年教育）。")
bullet("同一条技术链路，换一个交付对象，商业闭环从讲不通变成讲得通。")

h2("1.4 我们明确不做什么")
bullet("不做看图辨真伪。公文、票据、P 图取证属于鉴伪业务，既无资质也不该背书。图片只做 OCR，转成文字后走同一条核查链路。")
bullet("不做独立 App。老人不装，评委也不装，投入不产生任何评分收益。")
bullet("不追求什么都能判。查不到是常态，把查不到说清楚是功能，不是缺陷。")

# ---------------- 二 ----------------
h1("二、问题与场景")
h2("2.1 老人的信息环境")
bullet("微信群、朋友圈、短视频是主要信源，转发成本极低，纠错成本极高。")
bullet("对官方口吻缺乏分辨力，对熟人转发高度信任——这正是谣言与诈骗利用的两点。")
bullet("出问题往往发生在已经转了、已经买了、已经转了账之后，事后补救的代价远大于事前拦截。")
para("【待补】2～3 位老人与 2 位社区工作人员的访谈纪要、真实转发消息截图（脱敏），用于替换本段的定性描述。", size=9.5, color="B45309")

h2("2.2 现有工具为什么用不起来")
tbl("表 2  三类现有方案与它们的断点",
    ["方案", "做法", "断点", "我们的差异"],
    [["官方辟谣平台", "人工编辑，按关键词检索", "需要老人主动去搜，且要自己读懂", "把检索这一层替用户做完"],
     ["通用大模型问答", "直接回答是真的还是假的", "没有出处，无法验证，反而可能编造", "结论只由证据与规则产生"],
     ["搜索引擎", "返回一堆网页", "认知负担高，老人无法判断哪个可信", "证据分级，低等级不下结论"]],
    [3.2, 4.2, 4.4, 4.2])

h2("2.3 我们要解决的三个动作")
para("识别：这条消息到底在说什么，抽成一句可核查的主张。核实：有没有权威依据，依据到什么等级。转述：怎么用老人听得懂、并且愿意照做的方式说出来。三个动作，对应第三章的三个 Agent。")

# ---------------- 三 ----------------
h1("三、方案总述")
h2("3.1 交付物构成")
bullet("一套跑在 AgentArts 上的 Agent 编排：3 个 Agent、4 个自定义 Skill、1 个知识库、1 套评估集。")
bullet("一个手机优先的 H5 页面：扫码即用，微信内可直接打开，无需安装。")
bullet("一个可独立调用的 OCR Skill：把拍照 / 截图能力从主链路解耦，便于平台侧编排。")

h2("3.2 三个设计原则")
para("原则一：无据不判。", bold=True, indent=False, space=2)
para("知识库未命中、实时检索也没有权威结果时，系统明确回答「暂时查不到官方说法，先别信」，而不是让模型猜一个。这条既是伦理要求，也是可量化指标：查不到率。")
para("原则二：结论只由证据与规则产生，模型只负责说人话。", bold=True, indent=False, space=2)
para("大模型在本项目中只做四件辅助工作：抽取主张、生成检索词、判断页面是否在辟谣、把结论改写成大白话。它不参与真假判定，从机制上杜绝幻觉。")
para("原则三：证据分级。", bold=True, indent=False, space=2)
para("官方原文优于权威媒体，权威媒体优于网络线索。等级决定能不能下结论：只有官方等级才允许给出定性判断；网络线索只提供「有人在讨论」的参考。")

h2("3.3 与常见做法的差异")
tbl("表 3  方案对比",
    ["维度", "通用大模型问答", "辟谣网站", "本方案"],
    [["结论来源", "模型生成", "人工编辑", "证据加规则，模型不判真假"],
     ["出处", "常缺失", "有，但需自行查找", "必须携带，可追溯到原文"],
     ["查不到时", "倾向于编一个", "搜不到就返回空", "明确说明查不到，并给出下一步"],
     ["适老化", "无", "无", "大字、语音播报、可直接转发的短句"],
     ["可评估性", "难以量化", "难以量化", "有 200 条标注集与 5 项指标"]],
    [2.8, 4.2, 4.0, 5.0])

# ---------------- 四 ----------------
h1("四、Agent 编排")
h2("4.1 总体编排")
doc.add_picture(PNG, width=Cm(16))
doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
caption("图 1  「银龄核查助手」多 Agent 编排")

h2("4.2 三个 Agent 的职责与边界")
tbl("表 4  Agent 分工",
    ["Agent", "职责", "为什么单独拆"],
    [["意图与主张", "判断意图（核查 / 求助 / 闲聊）；把口语压成一句待核查主张；划分风险域（健康、钱财、政策、儿童）；信息过短时反问一句",
      "这一步决定全局，拆出来才能单独衡量主张抽取准确率"],
     ["核查（核心）", "知识库混合检索，证据分级，诈骗规则引擎，判级（高 / 中 / 暂无）。唯一允许下结论的 Agent",
      "输入是证据、输出是结构化证据对象，可独立替换检索方案"],
     ["转述", "适老化改写、语音播报稿、家庭转发文案、行动建议（96110 或官方渠道）",
      "只接收核查 Agent 输出的证据对象，不判真假，避免二次发挥时造假"]],
    [3.0, 6.6, 6.4])
para("一条硬约束：转述 Agent 只能拿到核查 Agent 输出的结构化证据，模型不参与真假判断。这条既写进方案，也写进代码，是无据不判从口号变成机制的地方。")

h2("4.3 四个自定义 Skill")
tbl("表 5  Skill 清单",
    ["Skill", "输入", "输出", "说明"],
    [["kb_search", "检索词、风险域", "候选证据（含等级、日期、来源）", "向量与关键词混合检索，阈值可调"],
     ["source_verify", "URL", "是否白名单、正文摘录", "域名后缀严格匹配，防止仿冒站"],
     ["scam_rules", "主张文本", "诈骗类型、风险等级", "规则引擎，覆盖冒充公检法、保健品、投资理财、补贴诈骗"],
     ["ocr_extract", "图片", "文字、耗时、识别状态", "只转文字不判真伪；原图不落盘；返回前打码"]],
    [3.0, 4.0, 4.6, 4.4])

h2("4.4 一次核查的完整时序")
para("① 用户在 H5 里输入文字、拍图或说话，前端压缩后提交。")
para("② 意图与主张 Agent 抽取主张并划分风险域；信息不足则反问。")
para("③ 核查 Agent 调用 kb_search 检索知识库，命中即进入证据分级；未命中再调 source_verify 与实时检索。")
para("④ 命中后由 scam_rules 复核风险类型；低等级证据不允许下定性结论。")
para("⑤ 转述 Agent 组装卡片：风险等级、结论、证据与出处、行动建议、可直接转发的短句。")
para("⑥ 前端渲染，支持一键语音播报与复制转发。")
para("性能目标：文字链路不超过 3 秒；图片链路（含 OCR）不超过 5 秒；超时即降级为暂未查到。")

# ---------------- 五 ----------------
h1("五、AgentArts 平台使用说明")
para("本章逐条对应赛题的五个考察环节，也是评审最可能追问的地方。")
tbl("表 6  赛题要求与我们的对应做法",
    ["赛题要求", "我们的做法", "可见证据"],
    [["智能体设计", "3 个 Agent 按识别、核实、转述拆分，职责单一、可独立替换", "图 1 编排图与平台配置截图【待补】"],
     ["工具编排", "4 个自定义 Skill 以 HTTP 接口接入，含独立 Skill 服务，不是纯提示词堆叠", "Skill 契约文档与接口自测记录"],
     ["知识接入", "20,122 条知识库，每条带来源等级、日期、来源三项元数据，按 300 至 500 字切分", "知识库截图与召回测试【待补】"],
     ["多 Agent 协作", "串行主干加条件分支，低等级证据不走下结论分支", "图 1 与分支配置截图【待补】"],
     ["效果评估", "200 条人工标注评估集，5 项指标，脚本自动跑分", "评估表【待测】"]],
    [3.2, 7.6, 5.2])

h2("5.2 完整闭环的五步，我们实际怎么走")
para("场景识别：从「子女转发可疑消息给老人」这个真实动作出发，发现核查的发起者其实是子女，于是调整了产品和用户模型。")
para("架构设计：先确定「结论必须可追溯」，才决定拆三个 Agent，而不是先写提示词再想架构。")
para("技能编排：把检索、白名单校验、诈骗规则、OCR 四件事从主链路拆成 Skill，便于单独调试与替换。")
para("调试优化：用首批 20 条失效样例反复调整检索阈值与提示词，记录每次改动前后的命中率。")
para("部署上线：在 AgentArts 上发布，H5 通过公网地址访问，评委扫码即可打开。")

# ---------------- 六 ----------------
h1("六、关键技术与工程细节")
h2("6.1 检索：混合而非单点")
para("中文口语与辟谣标题的表达差异很大，所谓「隔夜菜会中毒」与「剩菜致癌」在字面上几乎没有重合。单纯关键词匹配会大量漏检，因此采用向量检索召回、关键词重排、阈值可调的混合策略，阈值以评估集上的 F1 为准标定，而不是拍脑袋定一个数。")
h2("6.2 防假阳性：同一话题复核")
para("知识库命中不等于问的是同一件事。系统增加一步复核：由小模型判断这条辟谣记录与用户的问题是否属于同一传言，判定为否即丢弃该命中，宁可回答查不到。")
h2("6.3 图片入口：只转文字，不判真伪")
para("拍照与截图是老人最容易操作的入口。系统用华为云通用文字识别把图片转成文字，回填到输入框允许用户修改，再走同一条核查链路。原图仅在内存中处理，不落盘、不入库、不写日志。")
h2("6.4 隐私保护")
bullet("返回前对身份证号、银行卡号、手机号、验证码打码，见 ocr.mask_sensitive。")
bullet("不保存用户输入的原文与图片，仅保留匿名化的统计计数。")
bullet("不把用户内容传给任何第三方服务，OCR 与模型调用均在华为云内完成。")
h2("6.5 降级策略")
bullet("大模型不可用，退化为纯规则模式，功能不中断，只是表述更生硬。")
bullet("检索超时或全部失败，返回暂未查到，并建议咨询官方渠道或让子女核实。")
bullet("OCR 失败，提示重拍或改为粘贴文字，不让用户卡在报错页。")

# ---------------- 七 ----------------
h1("七、效果评估")
h2("7.1 评估集")
para("从公开辟谣语料中抽取 200 条，谣言与非谣言各半，覆盖健康、钱财、政策、儿童四个风险域，由团队人工标注标准答案与出处。评估集固定不变，每次改动模型或阈值后重跑，用于比较迭代效果。")
h2("7.2 指标定义")
tbl("表 7  评估指标",
    ["指标", "定义", "为什么重要"],
    [["准确率", "判定结果与标注一致的比例", "整体可用性"],
     ["漏判率", "谣言被判成查不到的比例", "最危险的错误：放过一条诈骗可能造成真实损失"],
     ["误判率", "真实信息被判成谣言的比例", "损害可信度，也会让老人错过正常政策"],
     ["无据率", "无法给出任何证据的比例", "越低越好，但绝不能靠编造来降低"],
     ["平均响应时间", "从提交到出卡", "老人等待耐心极低，超过 5 秒就会放弃"]],
    [3.0, 6.2, 6.8])
h2("7.3 当前状态")
para("评估集与跑分脚本正在建设，指标数值待实测后回填。方案阶段先把指标与口径定下来，避免后期只报好看的数字。", size=9.5, color="B45309")
tbl("表 8  指标目标值（待实测回填）",
    ["指标", "当前", "目标", "采集方式"],
    [["准确率", "【待实测】", "不低于 85%", "200 条评估集自动跑分"],
     ["漏判率", "【待实测】", "不高于 10%", "同上，单独统计"],
     ["误判率", "【待实测】", "不高于 8%", "同上"],
     ["无据率", "【待实测】", "不高于 25%", "同上"],
     ["平均响应", "【待实测】", "不超过 3 秒", "服务端埋点"]],
    [3.4, 4.0, 4.2, 4.4])

# ---------------- 八 ----------------
h1("八、合规与伦理边界")
bullet("不提供鉴伪服务：不判断公文、票据、图片本身的真伪，只判断这个说法有没有权威依据。")
bullet("不替代官方发布：政策类内容一律附加「以官方最新发布为准」，并给出原文链接。")
bullet("不提供医疗建议：健康类内容只做是否有权威辟谣的判断，不给用药与治疗意见。")
bullet("可追溯：每条结论都能回溯到具体证据条目与 URL，接受人工复核。")

# ---------------- 九 ----------------
h1("九、商业与落地")
h2("9.1 谁付费")
para("第一顺位是街道与社区，反诈宣传与基层治理考核有明确指标；第二顺位是养老机构与老年大学，可作为会员服务内容；第三顺位是银行网点与运营商营业厅，用于反诈宣传。老人本人不是付费方，但他是最终使用者，这个区分决定了定价方式。")
h2("9.2 定价与成本假设")
tbl("表 9  定价与成本（假设，需验证）",
    ["项目", "假设", "金额", "说明"],
    [["机构订阅", "按社区或街道年费", "【待定】", "参照反诈宣传物料采购单价估算，需实地询价"],
     ["云资源", "知识库与模型调用", "【待按账单核对】", "以实际调用量为准"],
     ["实施服务", "首次接入与培训", "【待定】", "含知识库本地化补充"]],
    [3.4, 4.0, 4.2, 4.4])
h2("9.3 落地路径")
para("第一步，1 个社区试点，换取真实使用数据与案例背书；第二步，复制到 3 个社区验证可复制性；第三步，通过街道或区级平台统一采购，形成区域覆盖。")

# ---------------- 十 ----------------
h1("十、实施计划（至 11 月 30 日）")
tbl("表 10  四周计划",
    ["时间", "目标", "交付物", "风险"],
    [["11/3 至 11/9", "平台跑通、知识库导入", "AgentArts 可用工程、召回测试记录", "知识库切分与召回不达标"],
     ["11/10 至 11/16", "四个 Skill 接入、编排完成", "完整链路可演示、Skill 契约文档", "平台工具接入方式不熟悉"],
     ["11/17 至 11/23", "评估与调优", "200 条评估表、阈值标定记录", "评估集标注耗时超预期"],
     ["11/24 至 11/30", "材料与提交", "方案书、PPT、3 分钟视频、报名表", "报名截止前材料不齐"]],
    [2.6, 3.4, 6.2, 3.8])

# ---------------- 十一 ----------------
h1("十一、团队分工")
tbl("表 11  分工",
    ["角色", "职责", "关键产出", "能力要求"],
    [["平台与编排", "AgentArts 工程搭建、Skill 接入、部署", "可运行工程与公网 Demo", "平台操作、接口调试"],
     ["知识与评估", "知识库建设、评估集标注、跑分与调优", "知识库、评估表", "数据处理、细致耐心"],
     ["产品与材料", "H5 交互、方案书、PPT、视频、答辩", "演示页面与全部材料", "前端基础、表达能力强"],
     ["指导教师", "平台资源、社区对接、评审把关", "试点社区、账号与额度", "行业与评审经验"]],
    [3.2, 5.0, 4.2, 3.6])

# ---------------- 十二 ----------------
h1("十二、风险与应对")
tbl("表 12  风险清单",
    ["风险", "影响", "应对", "触发信号"],
    [["知识库召回不达标", "大量回答查不到，演示难看", "改为混合检索、放宽阈值、扩充同义表达", "第 1 周召回测试低于 60%"],
     ["平台工具接入受限", "Skill 无法挂载", "先用平台内置能力兜底，自研 Skill 作为增强", "第 2 周仍无法接入"],
     ["评估集来不及标注", "无数据支撑", "缩减到 100 条，保证谣言类占比", "第 3 周仅完成不足一半"],
     ["被质疑是套壳大模型", "评分受损", "现场演示证据链与查不到分支，讲清模型不判真假", "问答预演被追问出处"],
     ["现场网络异常", "无法演示", "提前录制完整流程视频，准备本地降级版本", "赛前联调发现"]],
    [4.2, 3.4, 5.4, 3.0])

# ---------------- 附录 ----------------
h1("附录 A  赛题要求逐条对照")
tbl("表 13  对照表",
    ["赛题原文要求", "完成情况"],
    [["基于华为云 AgentArts 完成智能体的构建、编排与部署", "规划完成，第 1 至 2 周落地【待补截图】"],
     ["通过可视化 Demo 页面展示核心功能与交互流程", "H5 页面已具备，待部署公网地址"],
     ["体现工具编排、知识接入、多 Agent 协作、效果评估", "四项均有设计，评估数据待实测"],
     ["形成场景识别到部署上线的完整闭环", "五步均已执行，待补过程记录"],
     ["入围国赛后于华为云开发者社区发布分享帖", "未启动，计划 11 月下旬撰写初稿"]],
    [9.6, 6.4])

h1("附录 B  提交前必须补齐")
for i, t in enumerate([
        "社区与老人访谈 2 至 3 份，含脱敏截图",
        "知识库召回测试记录，20 条样例",
        "AgentArts 编排与配置截图 3 至 5 张",
        "200 条评估集与跑分结果表",
        "公网可访问的 Demo 地址与二维码",
        "3 分钟演示视频与答辩 PPT",
        "团队与指导教师信息，与报名表一致"], 1):
    para("%d. %s" % (i, t), indent=False, space=4)

h1("附录 C  参考资料")
para("1. 第十一届华为 ICT 大赛创新赛赛题二说明，华为云 AgentArts 平台。", indent=False, size=9.5, space=3)
para("2. 华为云 AgentArts 产品文档与用户指南。", indent=False, size=9.5, space=3)
para("3. 中国互联网联合辟谣平台公开辟谣内容，作为知识库来源。", indent=False, size=9.5, space=3)

doc.save(DOCX)
chk = Document(DOCX)
print("DOCX", os.path.getsize(DOCX), "paras", len(chk.paragraphs),
      "tables", len(chk.tables), "images", len(chk.inline_shapes))
