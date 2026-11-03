# -*- coding: utf-8 -*-
"""
知识库预处理：把 kb.json 变成 AgentArts 可以直接导入的格式

做的事：
  1. 清洗：去掉标题里的网站后缀、空条目、HTML 残留
  2. 去重：先按 URL，再按规范化标题
  3. 切分：正文超过 500 字的分块，重叠 50 字（平台检索按块召回）
  4. 补元数据：来源等级 tier、日期、领域、原文地址
  5. 出统计：每个领域的条目数、平均长度，用来判断知识库是否偏科

产物（tools/out/）：
  kb_import.jsonl    主格式，一行一个块
  kb_import.csv      兜底格式，平台只认表格时用
  kb_stats.md        统计报告

用法：
    python tools/prep_kb.py
"""

import csv
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
KB_NAME = sys.argv[1] if len(sys.argv) > 1 else "kb.json"
KB_PATH = os.path.join(PROJ, KB_NAME)
OUT_DIR = os.path.join(HERE, "out")

_stem = os.path.splitext(os.path.basename(KB_NAME))[0]
PREFIX = "kb_import" if _stem == "kb" else "kb_import_" + _stem.split("_", 1)[-1]

CHUNK = 500
OVERLAP = 50

# 官方站里混着大量"活动报道/工作动态"，它们不是可核查的传言，
# 留着只会让检索命中一条"某地举办辟谣沙龙"，答辩时很难看。
NOISE = ["沙龙", "举办", "启动仪式", "座谈会", "交流会", "培训班", "工作总结",
         "工作动态", "宣传海报", "海报展示", "访谈", "预告", "招募", "报名",
         "走进", "走进社区", "宣讲", "表彰", "揭牌", "上线运行", "正式启动"]
CLAIM_MARK = ["谣言", "辟谣", "不实", "假的", "真相", "回应", "网传", "？", "?"]

SITE_SUFFIX = re.compile(r"\s*[-—_|]\s*中国互联网联合辟谣平台\s*$")
CLEAN_WS = re.compile(r"[\s\u3000\xa0]+")

DOMAINS = {
    "健康": ["保健品", "偏方", "秘方", "治好", "根治", "降血糖", "降血压", "抗癌", "排毒",
             "停药", "药到病除", "祖传", "神药", "包治", "癌", "血糖", "血压", "养生"],
    "钱财": ["转账", "汇款", "验证码", "银行卡", "公检法", "安全账户", "洗钱", "刷单", "返利",
             "中奖", "免费领", "投资", "理财", "基金", "养老金", "补贴", "退税", "征信"],
    "政策": ["政策", "新规", "社保", "医保", "退休", "公积金", "个税", "发放", "缴费",
             "退休金", "补贴标准", "调整"],
    "儿童": ["儿童", "孩子", "学生", "校园", "未成年", "幼儿园", "小学", "家长", "小朋友"],
}

# 银龄相关度：命中越多越贴老人场景，导出给前端做优先展示
ELDER = ["老人", "老年", "退休", "养老", "高龄", "保健品", "降压", "降糖", "血糖", "血压",
         "三高", "抗癌", "偏方", "医保", "社保", "养老金", "补贴", "中风", "痴呆", "跌倒"]

TIER_LABEL = {
    "official": "官方原文",
    "dataset": "平台辟谣",
    "media": "媒体报道",
}


def elder_score(text):
    n = sum(1 for w in ELDER if w in text)
    return 3 if n >= 4 else (2 if n >= 2 else (1 if n >= 1 else 0))


def clean(s):
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)
    s = SITE_SUFFIX.sub("", s.strip())
    s = CLEAN_WS.sub(" ", s)
    return s.strip(" ，。、；：\t")


def domain_of(text):
    best, hit = "其他", 0
    for name, words in DOMAINS.items():
        n = sum(1 for w in words if w in text)
        if n > hit:
            best, hit = name, n
    return best


def normalize_title(t):
    return re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9]", "", t)


def split_chunks(text, size=CHUNK, overlap=OVERLAP):
    if len(text) <= size:
        return [text]
    out, i = [], 0
    while i < len(text):
        out.append(text[i:i + size])
        if i + size >= len(text):
            break
        i += size - overlap
    return out


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(KB_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    items = raw.get("items", [])
    print("原始条目:", len(items))

    seen_url, seen_title = set(), set()
    records = []
    dropped = {"no_title": 0, "no_text": 0, "dup_url": 0, "dup_title": 0, "noise": 0}

    for it in items:
        title = clean(it.get("title", ""))
        body = clean(it.get("snippet", ""))
        url = (it.get("url") or "").strip()
        tier = it.get("tier", "official")
        date = it.get("date", "") or ""

        if not title:
            dropped["no_title"] += 1
            continue
        if len(body) < 8:
            dropped["no_text"] += 1
            continue

        if tier == "official" and any(n in title for n in NOISE):
            dropped["noise"] += 1
            continue

        key_url = url or title
        if key_url in seen_url:
            dropped["dup_url"] += 1
            continue

        norm = normalize_title(title)
        if norm and norm in seen_title:
            dropped["dup_title"] += 1
            continue

        seen_url.add(key_url)
        if norm:
            seen_title.add(norm)

        dom = domain_of(title + " " + body)
        base = hashlib.sha1((url or title).encode("utf-8")).hexdigest()[:12]
        for i, ch in enumerate(split_chunks(body)):
            records.append({
                "id": "%s-c%d" % (base, i),
                "title": title,
                "content": title + "\n" + ch,
                "metadata": {
                    "url": url,
                    "tier": tier,
                    "tier_label": TIER_LABEL.get(tier, tier),
                    "date": date,
                    "domain": dom,
                    "elder": elder_score(title + body),
                    "source_name": it.get("source_name", ""),
                    "retrieved_at": it.get("retrieved_at", ""),
                    "chunk": i,
                    "chars": len(ch),
                },
            })

    jl = os.path.join(OUT_DIR, PREFIX + ".jsonl")
    with open(jl, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    cv = os.path.join(OUT_DIR, PREFIX + ".csv")
    with open(cv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "title", "content", "url", "tier", "date", "domain"])
        for r in records:
            m = r["metadata"]
            w.writerow([r["id"], r["title"], r["content"], m["url"], m["tier"], m["date"], m["domain"]])

    by_tier, by_dom, lens = {}, {}, []
    for r in records:
        by_tier[r["metadata"]["tier"]] = by_tier.get(r["metadata"]["tier"], 0) + 1
        by_dom[r["metadata"]["domain"]] = by_dom.get(r["metadata"]["domain"], 0) + 1
        lens.append(r["metadata"]["chars"])

    lines = []
    lines.append("# 知识库导入包统计\n")
    lines.append("- 原始条目：%d" % len(items))
    lines.append("- 入库条目（块）：%d" % len(records))
    lines.append("- 丢弃：无标题 %d，无正文 %d，URL 重复 %d，标题重复 %d，活动报道 %d" % (
        dropped["no_title"], dropped["no_text"], dropped["dup_url"],
        dropped["dup_title"], dropped["noise"]))
    lines.append("- 平均块长：%d 字" % (sum(lens) / max(len(lens), 1)))
    lines.append("\n## 按来源等级\n")
    for k, v in sorted(by_tier.items(), key=lambda x: -x[1]):
        lines.append("- %s：%d" % (k, v))
    lines.append("\n## 按领域\n")
    for k, v in sorted(by_dom.items(), key=lambda x: -x[1]):
        lines.append("- %s：%d" % (k, v))
    lines.append("\n## 提醒\n")
    lines.append("- 领域分布明显偏科时，答辩会被问「你们的知识库偏健康类」；"
                 "政策类偏少就补政策，用 kb.json 的来源重新抓。")
    lines.append("- tier 是 dataset 的条目只能当中风险处理，不要和官方条目混在一起下结论。")

    st = os.path.join(OUT_DIR, PREFIX + "_stats.md")
    with open(st, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print("块数:", len(records))
    print("按等级:", by_tier)
    print("按领域:", by_dom)
    print("平均块长: %.0f 字" % (sum(lens) / max(len(lens), 1)))
    print("输出:", jl)
    print("输出:", cv)
    print("输出:", st)


if __name__ == "__main__":
    main()
