# -*- coding: utf-8 -*-
import os
from PIL import Image, ImageDraw, ImageFont
OUT = r"C:\Users\风又音理233\Desktop\银龄核查助手\docs"
PNG = os.path.join(OUT, "银龄核查_Agent编排图.png")

def F(s, b=False):
    p = r"C:\Windows\Fonts\msyhbd.ttc" if b else r"C:\Windows\Fonts\msyh.ttc"
    if not os.path.exists(p): p = r"C:\Windows\Fonts\simhei.ttf"
    return ImageFont.truetype(p, s)

W, H = 1700, 940
img = Image.new("RGB", (W, H), "white")
d = ImageDraw.Draw(img)

def rr(x1,y1,x2,y2,r,fill,outline=None,wid=1):
    d.rounded_rectangle([x1,y1,x2,y2], radius=r, fill=fill, outline=outline, width=wid)

def ctext(cx,cy,s,f,fill):
    b = d.textbbox((0,0), s, font=f)
    d.text((cx-(b[2]-b[0])/2, cy-(b[3]-b[1])/2-b[1]), s, font=f, fill=fill)

def arrow(x1,y1,x2,y2,col="#94A3B8",wid=3):
    d.line([x1,y1,x2,y2], fill=col, width=wid)
    if abs(x2-x1) >= abs(y2-y1):
        s = 1 if x2 > x1 else -1
        d.polygon([(x2,y2),(x2-9*s,y2-6),(x2-9*s,y2+6)], fill=col)
    else:
        s = 1 if y2 > y1 else -1
        d.polygon([(x2,y2),(x2-6,y2-9*s),(x2+6,y2-9*s)], fill=col)

d.text((40,32), "图 1  「银龄核查助手」多 Agent 编排", font=F(34,True), fill="#111827")
d.text((40,80), "赛题二 · 华为云 AgentArts：3 个 Agent 分工 + 4 个自定义 Skill + 三级证据知识库，结论只由证据与规则产生",
       font=F(17), fill="#6B7280")

INK, SUB = "#1F2937", "#4B5563"
Y1, Y2 = 150, 560

# 输入
rr(30, Y1, 250, Y2, 14, "#EEF2F7", "#CBD5E1", 2)
ctext(140, Y1+34, "用户入口", F(22,True), "#334155")
for i, t in enumerate(["老人说一句话", "或发来语音", "", "子女转发", "一条可疑消息", "", "网格员上门", "核查记录"]):
    if t:
        ctext(140, Y1+80+i*36, t, F(16), SUB)

# Agent 1
rr(290, Y1, 620, Y2, 16, "#E8F1FB", "#93C5FD", 2)
d.text((310, Y1+16), "① 意图与主张 Agent", font=F(21,True), fill="#1E3A8A")
for i, t in enumerate(["意图分类：核查 / 求助 / 闲聊", "主张抽取：压成一句待核查说法", "风险域：健康 · 钱财 · 政策 · 儿童", "过短或含糊 → 反问一句"]):
    d.text((312, Y1+64+i*46), "· " + t, font=F(16), fill=INK)

# Agent 2
rr(660, Y1-20, 1090, Y2+20, 16, "#FDECEC", "#F87171", 3)
d.text((680, Y1-4), "② 核查 Agent（核心）", font=F(21,True), fill="#991B1B")
for i, t in enumerate(["知识库混合检索（向量 + 关键词）", "证据分级：官方 > 央媒 > 网络线索", "诈骗规则引擎：关键词 → 类型 → 风险", "判级：高风险 / 中风险 / 暂无结论", "查不到就说查不到（无据不判）"]):
    d.text((682, Y1+46+i*46), "· " + t, font=F(16), fill=INK)

# Agent 3
rr(1130, Y1, 1440, Y2, 16, "#FEF6E7", "#FBBF24", 2)
d.text((1150, Y1+16), "③ 转述 Agent", font=F(21,True), fill="#92400E")
for i, t in enumerate(["适老化改写：大白话，短句", "语音播报稿（给看不清的老人）", "家庭转发文案（发给子女）", "行动建议：96110 / 官方渠道"]):
    d.text((1152, Y1+64+i*46), "· " + t, font=F(16), fill=INK)

# 输出
rr(1470, Y1, 1670, Y2, 16, "#E9F7EF", "#34D399", 2)
ctext(1570, Y1+34, "核查卡片", F(20,True), "#065F46")
for i, t in enumerate(["风险等级", "结论", "证据 + 出处", "行动建议", "一键转发"]):
    ctext(1570, Y1+86+i*44, t, F(16), SUB)

for x in (258, 628, 1100, 1448):
    arrow(x+4, (Y1+Y2)//2, x+28, (Y1+Y2)//2)

# 底部平台资产
BY1, BY2 = 660, 880
rr(30, BY1, 1670, BY2, 16, "#F8FAFC", "#E2E8F0", 2)
d.text((52, BY1+14), "AgentArts 平台资产", font=F(19,True), fill="#334155")

items = [
    ("知识库", ["kb.json 全量导入", "doc 打 tier / date / source", "切分 300–500 字"]),
    ("自定义 Skill ×4", ["kb_search 混合检索", "source_verify 白名单校验", "scam_rules 诈骗规则", "safe_rewrite 模板改写"]),
    ("评估集", ["200 条人工标注", "准确率 / 漏判率", "误判率 / 响应时长"]),
    ("可视化 Demo", ["H5 核查卡页面", "公网可访问链接", "现场可实时演示"]),
]
bx1, bx2 = 52, 1648
bw = (bx2-bx1-3*18)/4
for i,(t,lines) in enumerate(items):
    x = bx1 + i*(bw+18)
    rr(x, BY1+46, x+bw, BY2-14, 10, "white", "#CBD5E1", 2)
    ctext(x+bw/2, BY1+66, t, F(17,True), "#0F172A")
    for j,ln in enumerate(lines):
        ctext(x+bw/2, BY1+100+j*26, ln, F(14), SUB)

# 虚线：知识库 -> 核查 Agent
for x0 in (330, 790, 1250):
    for xx in range(x0, x0+40, 8):
        d.line([xx, BY1-6, xx+4, BY1-6], fill="#CBD5E1", width=2)

d.text((40, H-34), "注：箭头为调用方向；③ 的输入只能来自 ② 输出的证据对象，模型不参与判真判假（对应「无据不判」原则）。",
       font=F(15), fill="#9CA3AF")

img.save(PNG, "PNG")
print("OK", os.path.getsize(PNG))
