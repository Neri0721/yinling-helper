# -*- coding: utf-8 -*-
"""生成初赛提交材料包（信息表 / 方案书 V1.1 / 答辩 PPT / 视频脚本）"""

import os
import shutil

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from pptx import Presentation
from pptx.dml.color import RGBColor as PRGB
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt as PPt

PROJ = r"C:\Users\风又音理233\Desktop\银龄核查助手"
OUT = os.path.join(PROJ, "submission")
ARCH = os.path.join(PROJ, "docs", "银龄核查_Agent编排图.png")
BASE_DOC = os.path.join(PROJ, "docs", "银龄核查助手_作品设计方案_V1.0.docx")

RED = "B3121D"
INK = "1F2937"
GREY = "6B7280"

os.makedirs(OUT, exist_ok=True)


# ---------------------------------------------------------------- docx 工具
def setrun(r, name):
    r.font.name = name
    r._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), name)


def new_doc():
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.top_margin = sec.bottom_margin = Cm(2.2)
    sec.left_margin = sec.right_margin = Cm(2.4)
    st = doc.styles["Normal"]
    st.font.name = "宋体"
    st.font.size = Pt(10.5)
    st.element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "宋体")
    return doc


def para(doc, text, size=10.5, bold=False, color=None, align=None, space=6, indent=True, name="宋体"):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space)
    p.paragraph_format.line_spacing = 1.5
    if indent:
        p.paragraph_format.first_line_indent = Pt(21)
    if align is not None:
        p.alignment = align
    r = p.add_run(text)
    r.font.size = Pt(size)
    r.bold = bold
    setrun(r, name)
    if color:
        r.font.color.rgb = RGBColor.from_string(color)
    return p


def heading(doc, text, size=15):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(6)
    r = p.add_run(text)
    r.font.size = Pt(size)
    r.bold = True
    r.font.color.rgb = RGBColor.from_string(RED)
    setrun(r, "微软雅黑")
    return p


def table(doc, headers, rows, widths=None, size=9):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]
        c.text = ""
        r = c.paragraphs[0].add_run(h)
        r.bold = True
        r.font.size = Pt(size)
        setrun(r, "微软雅黑")
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            r = cells[i].paragraphs[0].add_run(str(v))
            r.font.size = Pt(size)
            setrun(r, "宋体")
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Cm(w)
    return t


# ---------------------------------------------------------------- 1 信息表
def build_info():
    doc = new_doc()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("第十一届华为 ICT 大赛（创新赛）参赛作品信息表")
    r.font.size = Pt(18)
    r.bold = True
    setrun(r, "微软雅黑")
    para(doc, "赛题二：基于华为云 AgentArts 智能体开发平台打造 Agent", size=11,
         color=GREY, align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, space=16)

    heading(doc, "一、基本信息")
    table(doc, ["项目", "内容"],
          [["作品名称", "银龄核查助手"],
           ["参赛赛题", "赛题二 · 基于华为云 AgentArts 智能体开发平台打造 Agent"],
           ["应用方向", "行业赋能型（基层治理与社区养老）"],
           ["参赛院校", "成都东软学院 计算机与软件学院"],
           ["团队成员", "（待填）________　________　________"],
           ["指导教师", "（待填）________"],
           ["团队联系人", "（待填）姓名 / 手机 / 邮箱"]],
          [4.0, 12.0])

    heading(doc, "二、作品简介（200 字以内）")
    para(doc, "「银龄核查助手」是一个部署在华为云 AgentArts 上的多智能体应用。子女或社区网格员把长辈收到的可疑消息转发进来（文字、截图或语音），系统给出风险等级、结论、可追溯的权威出处，以及一句能让老人听懂的转述。它的核心主张是「无据不判」：结论只能由证据与规则产生，查不到就明确说查不到，模型只负责把话说得像人话。")

    heading(doc, "三、核心创新点")
    table(doc, ["序号", "创新点", "说明"],
          [["1", "检测—归因—转述闭环", "不止判断真假，还给处置建议与可直接转发的短句"],
           ["2", "三级证据分级", "官方原文 / 平台辟谣 / 媒体报道，等级决定能否下定性结论"],
           ["3", "双用户模型", "发起核查的是子女与网格员，接收结论的才是老人"],
           ["4", "可量化的「不知道」", "无据率作为一级指标，敢说查不到是产品能力而非缺陷"]],
          [1.4, 5.0, 9.6])

    heading(doc, "四、技术方案要点")
    table(doc, ["层面", "实现"],
          [["智能体", "3 个 Agent：意图与主张 / 核查 / 转述，串行编排 + 条件分支"],
           ["工具", "4 个自定义 Skill：kb_search、source_verify、scam_rules、ocr_extract"],
           ["知识", "银龄子集 3,188 块，官方原文 216 块 / 107 篇，每条带来源、日期、等级"],
           ["评估", "20 条样例结构校验通过；200 条评估集建设中"],
           ["部署", "华为云 AgentArts（公测权限申请中，已提交、待审核）"]],
          [3.0, 13.0])

    heading(doc, "五、当前进度说明")
    para(doc, "代码工程已完成并通过 12 项自测（编译、健康检查、文字与图片核查、代理、三个 Skill、提示词结构校验、召回基线、手机页检查）。AgentArts 公测申请已提交，等待平台审核；审核通过后完成三个 Agent 的编排与部署，并补充平台截图。")

    doc.save(os.path.join(OUT, "01_参赛作品信息表.docx"))
    print("OK 01_参赛作品信息表.docx")


# ---------------------------------------------------------------- 2 方案书 V1.1
def build_plan():
    dst = os.path.join(OUT, "02_作品设计方案_V1.1.docx")
    shutil.copyfile(BASE_DOC, dst)
    doc = Document(dst)
    doc.add_page_break()
    p = doc.add_paragraph()
    r = p.add_run("附录 D　平台部署进度与材料说明")
    r.font.size = Pt(15)
    r.bold = True
    r.font.color.rgb = RGBColor.from_string(RED)
    setrun(r, "微软雅黑")

    para(doc, "本稿为初赛提交版本。截至 2026 年 11 月 14 日，作品在工程侧已完成并通过 12 项自测；平台侧受华为云 AgentArts 公测权限审核影响，编排与部署尚未完成，相关截图与指标将在权限开通后补充。")
    para(doc, "已完成的工程能力（均可在本地复现）：")
    for t in ["12 项自测全绿：编译、健康检查、文字核查、图片核查、代理未配置降级、三个 Skill、提示词结构校验、召回基线、手机页检查",
              "知识库：银龄子集 3,188 块，官方原文 216 块（107 篇），每条带来源、日期、证据等级",
              "召回基线：20 条测试题，recall@1 17/20、@3 18/20、@5 18/20",
              "手机页：首屏双入口（拍照 / 说话），单页资源 24.6 KB"]:
        para(doc, "· " + t, indent=False, space=3)

    para(doc, "平台侧的当前状态：")
    for t in ["AgentArts 公测申请已提交，页面显示「申请已成功受理，我们将尽快完成审核」",
              "控制台「创建智能体」按钮为灰色，说明权限尚未下发",
              "已保存申请状态截图作为过程证据"]:
        para(doc, "· " + t, indent=False, space=3)

    para(doc, "权限开通后 48 小时内的补全计划：建知识库 → 导入 3,188 块 → 挂载 4 个 Skill → 三 Agent 串联 → 部署取公网地址 → 补平台截图与真实指标。")

    doc.save(dst)
    print("OK 02_作品设计方案_V1.1.docx")


# ---------------------------------------------------------------- 3 答辩 PPT
def build_pptx():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    W, H = prs.slide_width, prs.slide_height
    blank = prs.slide_layouts[6]

    def slide():
        return prs.slides.add_slide(blank)

    def tx(s, text, left, top, width, height, size=20, bold=False, color=INK, align=PP_ALIGN.LEFT, name="微软雅黑"):
        box = s.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
        tf = box.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = align
        r = p.add_run()
        r.text = text
        r.font.size = PPt(size)
        r.font.bold = bold
        r.font.name = name
        r.font.color.rgb = PRGB.from_string(color)
        return box

    def bullets(s, items, left, top, width, height, size=18, color=INK, gap=10):
        box = s.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
        tf = box.text_frame
        tf.word_wrap = True
        for i, it in enumerate(items):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.space_after = PPt(gap)
            r = p.add_run()
            r.text = it
            r.font.size = PPt(size)
            r.font.name = "微软雅黑"
            r.font.color.rgb = PRGB.from_string(color)

    def band(s, y, h=0.09, color=RED):
        from pptx.enum.shapes import MSO_SHAPE
        sh = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(y), W, Inches(h))
        sh.fill.solid()
        sh.fill.fore_color.rgb = PRGB.from_string(color)
        sh.line.fill.background()

    def head(s, title, kicker=""):
        band(s, 0)
        tx(s, title, 0.7, 0.35, 11.9, 0.9, size=32, bold=True, color=RED)
        if kicker:
            tx(s, kicker, 0.72, 1.15, 11.9, 0.5, size=15, color=GREY)

    def footer(s, n):
        tx(s, "银龄核查助手 · 赛题二", 0.7, 6.95, 8, 0.4, size=11, color=GREY)
        tx(s, str(n), 12.2, 6.95, 0.6, 0.4, size=11, color=GREY, align=PP_ALIGN.RIGHT)

    # 1 封面
    s = slide()
    band(s, 0, 0.14)
    tx(s, "银龄核查助手", 0.9, 2.0, 11.5, 1.2, size=48, bold=True, color=RED)
    tx(s, "给子女和社区用的反谣反诈核查智能体", 0.95, 3.25, 11.5, 0.7, size=24, color=INK)
    tx(s, "第十一届华为 ICT 大赛 · 创新赛 · 赛题二", 0.95, 4.3, 11.5, 0.5, size=16, color=GREY)
    tx(s, "成都东软学院 计算机与软件学院", 0.95, 4.85, 11.5, 0.5, size=16, color=GREY)
    tx(s, "团队成员：________　________　________　　指导教师：________", 0.95, 5.35, 11.5, 0.5, size=14, color=GREY)

    # 2 一句话
    s = slide()
    head(s, "一句话说清它是什么")
    tx(s, "子女把长辈收到的一条可疑消息转发进来，", 0.9, 1.9, 11.5, 0.6, size=24)
    tx(s, "系统给出风险等级、结论、可追溯的出处，", 0.9, 2.6, 11.5, 0.6, size=24)
    tx(s, "以及一句老人听得懂、照着做的话。", 0.9, 3.3, 11.5, 0.6, size=24)
    bullets(s, ["不是「又一个问答机器人」—— 结论必须带出处", "查不到就明说 —— 不会为了好看编一个答案",
                "说人话 —— 最终输出是给七十岁的人看的"], 0.95, 4.4, 11.5, 1.8, size=19, color=GREY)
    footer(s, 2)

    # 3 双用户
    s = slide()
    head(s, "我们服务的其实是两个人", "这是与多数同类作品最大的不同")
    tx(s, "发起核查的人 ≠ 接收结论的人", 0.9, 1.75, 11.5, 0.6, size=22, bold=True, color=INK)
    table_rows = [["发起者", "子女、社区网格员", "有能力判断可疑，有动力去查"],
                  ["接收者", "老人", "只关心能不能信、要不要做"]]
    t = s.shapes.add_table(2, 3, Inches(0.9), Inches(2.6), Inches(11.5), Inches(1.5)).table
    for i, row in enumerate(table_rows):
        for j, v in enumerate(row):
            c = t.cell(i, j)
            c.text = v
            for p in c.text_frame.paragraphs:
                p.runs[0].font.size = PPt(16)
                p.runs[0].font.name = "微软雅黑"
    tx(s, "所以三个端各有各的人：老人看结论、子女发起、网格员批量。", 0.9, 4.5, 11.5, 0.5, size=18, color=RED)
    tx(s, "把两个用户混为一谈，就会做成「让老人自己打开网页输入一句话」—— 而这恰恰是老人不会做的事。",
       0.9, 5.15, 11.5, 0.9, size=16, color=GREY)
    footer(s, 3)

    # 4 现有断点
    s = slide()
    head(s, "现有方案为什么用不起来", "不是没人做，是都断在同一个地方")
    rows = [["辟谣平台", "要老人主动去搜，还要自己读懂", "把检索这层替用户做完"],
            ["大模型问答", "没有出处，无法验证，可能编造", "结论只由证据与规则产生"],
            ["搜索引擎", "返回一堆网页，判断不了哪个可信", "证据分级，低等级不下结论"]]
    t = s.shapes.add_table(3, 3, Inches(0.9), Inches(1.85), Inches(11.5), Inches(2.6)).table
    heads = ["现有方案", "断点", "我们的差异"]
    for j, h in enumerate(heads):
        c = t.cell(0, j) if False else None
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            cell = t.cell(i, j)
            cell.text = v
            for p in cell.text_frame.paragraphs:
                p.runs[0].font.size = PPt(14)
                p.runs[0].font.name = "微软雅黑"
    tx(s, "共同点：它们都在回答「真的假的」，而用户真正卡住的是「我凭什么信」。", 0.9, 4.85, 11.5, 0.6, size=18, color=RED)
    footer(s, 4)

    # 5 三原则
    s = slide()
    head(s, "三条不妥协的设计原则")
    items = [("无据不判", "证据为空时明确回答「暂时查不到官方说法」，不许模型猜"),
             ("模型不判真假", "大模型只做四件事：抽主张、生成检索词、判页面是否辟谣、把结论改写成大白话"),
             ("证据分级", "官方原文 > 权威媒体 > 网络线索；只有官方等级才允许下定性结论")]
    y = 1.85
    for name, desc in items:
        tx(s, name, 0.9, y, 3.4, 0.6, size=22, bold=True, color=RED)
        tx(s, desc, 4.4, y + 0.05, 8.1, 0.9, size=16, color=INK)
        y += 1.55
    footer(s, 5)

    # 6 架构图
    s = slide()
    head(s, "系统架构", "端侧 → 接入 → 智能体编排 → 模型与知识 → 业务数据")
    pic_h = Inches(4.85)
    from PIL import Image as PILImage
    iw, ih = PILImage.open(ARCH).size
    pic_w = int(pic_h * iw / ih)
    left = int((W - pic_w) / 2)
    s.shapes.add_picture(ARCH, left, Inches(1.72), height=pic_h)
    footer(s, 6)

    # 7 三个 Agent
    s = slide()
    head(s, "三个 Agent：按「能否独立替换」拆", "不是按功能数量拆")
    rows = [["① 意图与主张", "判断意图、把口语压成一句待核查主张、划分风险域", "可单独衡量抽取准确率"],
            ["② 核查（核心）", "检索、证据分级、诈骗规则、判级", "唯一允许下结论的 Agent"],
            ["③ 转述", "适老化改写、语音稿、转发文案、行动建议", "只拿到证据对象，不判真假"]]
    t = s.shapes.add_table(3, 3, Inches(0.9), Inches(1.9), Inches(11.5), Inches(2.8)).table
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            cell = t.cell(i, j)
            cell.text = v
            for p in cell.text_frame.paragraphs:
                p.runs[0].font.size = PPt(14)
                p.runs[0].font.name = "微软雅黑"
    tx(s, "硬约束：③ 只能拿 ② 输出的结构化证据 —— 模型不参与真假判断，从机制上杜绝幻觉。",
       0.9, 5.05, 11.5, 0.6, size=17, color=RED)
    footer(s, 7)

    # 8 四个 Skill
    s = slide()
    head(s, "四个自定义 Skill", "不是提示词堆叠，是真实的可调用能力")
    rows = [["kb_search", "8791", "在银龄子集里检索，返回带等级与出处的证据"],
            ["source_verify", "8792", "域名白名单校验 + 抓正文，防仿冒站"],
            ["scam_rules", "8793", "四类诈骗识别：冒充公检法 / 保健品会销 / 投资理财 / 补贴退税"],
            ["ocr_extract", "8790", "图片转文字，只转不判；原图不落盘，返回前打码"]]
    t = s.shapes.add_table(4, 3, Inches(0.9), Inches(1.9), Inches(11.5), Inches(3.0)).table
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            cell = t.cell(i, j)
            cell.text = v
            for p in cell.text_frame.paragraphs:
                p.runs[0].font.size = PPt(14)
                p.runs[0].font.name = "微软雅黑"
    tx(s, "每个 Skill 独立端口、独立 /health、独立契约文档，可单独替换与降级。", 0.9, 5.3, 11.5, 0.5, size=16, color=GREY)
    footer(s, 8)

    # 9 时序
    s = slide()
    head(s, "一次核查的完整时序", "目标：文字 ≤3 秒，图片 ≤5 秒")
    steps = ["① 工位端拍照 / 说话 / 贴文字，前端压缩后提交",
             "② 意图与主张 Agent 抽取主张并划分风险域，信息不足则反问",
             "③ 核查 Agent 调 kb_search，命中即做证据分级",
             "④ 未命中再调 source_verify 与实时检索，仍无则 no_evidence",
             "⑤ scam_rules 复核诈骗类型，低等级证据不得下定性结论",
             "⑥ 转述 Agent 组装卡片：等级 / 结论 / 证据 / 建议 / 转发句",
             "⑦ 语音播报 + 一键复制转发"]
    bullets(s, steps, 0.9, 1.9, 11.5, 4.2, size=17, gap=12)
    footer(s, 9)

    # 10 证据分级
    s = slide()
    head(s, "证据分级怎么落到产品上")
    rows = [["官方原文", "高风险 / 可定性", "中国互联网联合辟谣平台、政府白名单"],
            ["平台辟谣", "中风险 / 不给定性", "微博社区辟谣等公开语料"],
            ["网络线索", "仅供参考", "问答、百科、论坛；不冒充结论"],
            ["无证据", "暂无权威结论", "明确说查不到，并给出核实路径"]]
    t = s.shapes.add_table(4, 3, Inches(0.9), Inches(1.9), Inches(11.5), Inches(3.2)).table
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            cell = t.cell(i, j)
            cell.text = v
            for p in cell.text_frame.paragraphs:
                p.runs[0].font.size = PPt(14)
                p.runs[0].font.name = "微软雅黑"
    tx(s, "这一层分级，就是「凭什么信」的答案。", 0.9, 5.45, 11.5, 0.5, size=18, color=RED)
    footer(s, 10)

    # 11 知识库
    s = slide()
    head(s, "知识库：可追溯，而不是「很多条」")
    rows = [["规模", "银龄子集 3,188 块（源语料 20,122 条）"],
            ["官方原文", "216 块 / 107 篇，正文已回抓，平均 365 字"],
            ["元数据", "来源机构、发布日期、抓取时间、证据等级、银龄相关度"],
            ["来源", "中国互联网联合辟谣平台 + 公开辟谣语料"],
            ["召回基线", "20 题：@1 17/20、@3 18/20、@5 18/20"]]
    t = s.shapes.add_table(5, 2, Inches(0.9), Inches(1.85), Inches(11.5), Inches(3.6)).table
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            cell = t.cell(i, j)
            cell.text = v
            for p in cell.text_frame.paragraphs:
                p.runs[0].font.size = PPt(15)
                p.runs[0].font.name = "微软雅黑"
    footer(s, 11)

    # 12 评估
    s = slide()
    head(s, "效果评估怎么算", "没有数字的「效果不错」等于没有")
    rows = [["准确率", "判定与标注一致的比例", "≥85%"],
            ["漏判率", "谣言被判成「查不到」的比例", "≤10%"],
            ["误判率", "真信息被判成谣言的比例", "≤8%"],
            ["无据率", "无法给出任何证据的比例", "≤25%"],
            ["平均响应", "从提交到出卡", "≤3 秒"]]
    t = s.shapes.add_table(5, 3, Inches(0.9), Inches(1.85), Inches(11.5), Inches(3.2)).table
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            cell = t.cell(i, j)
            cell.text = v
            for p in cell.text_frame.paragraphs:
                p.runs[0].font.size = PPt(15)
                p.runs[0].font.name = "微软雅黑"
    tx(s, "当前状态：20 条样例通过结构校验；200 条评估集建设中，目标值将在实测后回填。",
       0.9, 5.45, 11.5, 0.6, size=15, color=GREY)
    footer(s, 12)

    # 13 边界
    s = slide()
    head(s, "边界：哪些事我们不做")
    bullets(s, ["不判断图片、公文、票据本身的真伪 —— 鉴伪需要资质，我们不做背书",
                "不替代官方发布 —— 政策类一律提示「以官方最新发布为准」并给出原文",
                "不提供医疗建议 —— 只判断「有没有权威辟谣」，不给用药意见",
                "不保存原图 —— 只在内存处理，返回前对卡号、身份证、验证码打码"],
            0.9, 1.95, 11.5, 3.6, size=19, gap=18)
    tx(s, "把边界说清楚，是为了让「能做什么」更可信。", 0.9, 5.6, 11.5, 0.6, size=17, color=RED)
    footer(s, 13)

    # 14 商业
    s = slide()
    head(s, "谁为它付费")
    rows = [["第一顺位", "街道与社区", "反诈宣传与基层治理有明确考核指标"],
            ["第二顺位", "养老机构、老年大学", "可作为会员服务内容"],
            ["第三顺位", "银行网点、运营商营业厅", "反诈宣传物料与工具"]]
    t = s.shapes.add_table(3, 3, Inches(0.9), Inches(1.9), Inches(11.5), Inches(2.3)).table
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            cell = t.cell(i, j)
            cell.text = v
            for p in cell.text_frame.paragraphs:
                p.runs[0].font.size = PPt(15)
                p.runs[0].font.name = "微软雅黑"
    tx(s, "老人本人不是付费方，但他是最终使用者 —— 这个区分决定了定价方式。", 0.9, 4.55, 11.5, 0.6, size=17, color=RED)
    tx(s, "路径：1 个社区试点 → 复制到 3 个社区 → 区域统一采购。", 0.9, 5.15, 11.5, 0.5, size=16, color=GREY)
    footer(s, 14)

    # 15 进度
    s = slide()
    head(s, "当前进度（如实说明）", "2026-11-14")
    rows = [["已完成", "代码工程 12 项自测全绿；知识库 3,188 块；三个 Skill；提示词资产；手机页双入口"],
            ["进行中", "AgentArts 公测权限审核中（已提交申请，创建按钮待放开）"],
            ["待补齐", "平台部署与截图、200 条评估集、答辩视频"]]
    t = s.shapes.add_table(3, 2, Inches(0.9), Inches(1.9), Inches(11.5), Inches(2.4)).table
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            cell = t.cell(i, j)
            cell.text = v
            for p in cell.text_frame.paragraphs:
                p.runs[0].font.size = PPt(14)
                p.runs[0].font.name = "微软雅黑"
    tx(s, "权限开通后 48 小时内完成：建库 → 导数据 → 挂 Skill → 三 Agent 串联 → 部署取公网地址。",
       0.9, 4.65, 11.5, 0.7, size=16, color=INK)
    footer(s, 15)

    # 16 团队
    s = slide()
    head(s, "团队分工")
    rows = [["平台与编排", "AgentArts 工程、Skill 挂载、部署"],
            ["知识与评估", "知识库建设、评估集标注、跑分调优"],
            ["产品与材料", "H5 交互、方案书、PPT、视频、答辩"],
            ["指导教师", "平台资源、社区对接、评审把关"]]
    t = s.shapes.add_table(4, 2, Inches(0.9), Inches(1.95), Inches(11.5), Inches(2.8)).table
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            cell = t.cell(i, j)
            cell.text = v
            for p in cell.text_frame.paragraphs:
                p.runs[0].font.size = PPt(15)
                p.runs[0].font.name = "微软雅黑"
    footer(s, 16)

    # 17 结尾
    s = slide()
    band(s, 3.4, 0.1)
    tx(s, "我们做的不是一个会聊天的机器人，", 0.9, 2.2, 11.5, 0.8, size=28, color=INK)
    tx(s, "而是一个敢说「我不知道」的核查员。", 0.9, 3.0, 11.5, 0.8, size=28, bold=True, color=RED)
    tx(s, "谢谢各位老师。", 0.9, 4.6, 11.5, 0.6, size=20, color=GREY)

    # 统一表格样式：红表头 + 交替浅底
    def paint(tbl):
        cols = len(tbl.columns)
        rows = len(tbl.rows)
        for i in range(rows):
            for j in range(cols):
                cell = tbl.cell(i, j)
                cell.fill.solid()
                if i == 0:
                    cell.fill.fore_color.rgb = PRGB.from_string(RED)
                    rgb = "FFFFFF"
                else:
                    cell.fill.fore_color.rgb = PRGB.from_string("F7F8FA" if i % 2 else "FFFFFF")
                    rgb = INK
                for p in cell.text_frame.paragraphs:
                    for r in p.runs:
                        r.font.color.rgb = PRGB.from_string(rgb)
                        if i == 0:
                            r.font.bold = True
        for i in range(rows):
            tbl.rows[i].height = Inches(0.5)

    for sl in prs.slides:
        for sh in sl.shapes:
            if getattr(sh, "has_table", False) and sh.has_table:
                paint(sh.table)

    path = os.path.join(OUT, "03_答辩PPT.pptx")
    prs.save(path)
    print("OK 03_答辩PPT.pptx  slides=%d" % len(prs.slides))


# ---------------------------------------------------------------- 4 视频脚本
def build_video():
    doc = new_doc()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("3 分钟演示视频 · 分镜脚本")
    r.font.size = Pt(18)
    r.bold = True
    setrun(r, "微软雅黑")
    para(doc, "总时长控制在 2 分 50 秒以内，留 10 秒缓冲。台词照读即可，不必背。",
         size=10.5, color=GREY, align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, space=16)

    heading(doc, "一、镜头表")
    table(doc, ["时间", "画面", "台词（照读）", "备注"],
          [["0:00–0:15", "手机微信界面，长辈发来一条「养老金补发」消息", "我妈昨天在群里看到这条，问我是不是真的。", "真机录屏，界面打码"],
           ["0:15–0:30", "打开小程序 / 网页，首页两个大按钮", "她不会打字，所以我替她查。老人真正会做的动作，是转发给子女。", "点「拍张照」"],
           ["0:30–0:55", "拍照上传，黄色提示条，识别文字回填", "拍一张截图就能查。识别出的文字还能改。", "演示模式要打码说明"],
           ["0:55–1:25", "卡片出现：风险等级、结论、证据、出处", "结论旁边一定有出处：哪个平台、哪天发的。这是我们的底线。", "停顿 2 秒给评委看清"],
           ["1:25–1:50", "换一条查不到的，出现「暂无权威结论」", "查不到的时候，它会直接说查不到——不会编一个答案糊弄老人。", "这是全片重点"],
           ["1:50–2:10", "点语音播报，手机念出结论", "看不清字的老人，可以听。", "音量调大"],
           ["2:10–2:30", "切换到电脑，三个 Agent 编排图", "背后是三个智能体：抽主张、核证据、说人话。模型不判真假。", "放编排图"],
           ["2:30–2:50", "回到手机，点「发给子女」，复制出短句", "最后一步，把结论发回家庭群。", "结尾定格"],
           ["2:50–3:00", "标题页：作品名 + 团队", "银龄核查助手，谢谢。", "黑底白字"]],
          [2.4, 5.2, 6.6, 3.0])

    heading(doc, "二、录制要点")
    for t in ["全程真机录屏，不要用 PPT 动画冒充产品",
              "「查不到」那一段必须保留，它是评委记住你们的地方",
              "OCR 若仍是演示模式，在画面上加一行小字说明「未接入识别服务」，不要装作识别成功",
              "录音用手机自带麦克风即可，环境要安静，语速比平时慢一点",
              "导出 1080p、MP4，文件控制在 100 MB 以内"]:
        para(doc, "· " + t, indent=False, space=4)

    heading(doc, "三、素材清单（录前准备）")
    table(doc, ["序号", "素材", "怎么来"],
          [["1", "三条演示问题", "「养老金补发 800 元」（查不到）、「喝骨头汤补钙」（能查到）、「冒充公检法」（高风险）"],
           ["2", "一张可疑消息截图", "自己拼的图即可，不要用真实聊天记录"],
           ["3", "编排图", "docs/银龄核查_Agent编排图.png"],
           ["4", "片头片尾", "用 PPT 第 1 页和最后一页导出图片"]],
          [1.2, 4.4, 10.4])

    doc.save(os.path.join(OUT, "04_演示视频脚本.docx"))
    print("OK 04_演示视频脚本.docx")


if __name__ == "__main__":
    build_info()
    build_plan()
    build_pptx()
    build_video()
    print("DONE ->", OUT)
