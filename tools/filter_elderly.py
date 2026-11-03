# -*- coding: utf-8 -*-
"""
筛出"银龄相关"子集

背景：19,372 条里，真正跟老人（健康、养老、社保、诈骗、补贴）相关的只有约 360 条，
      其余 97% 是泛社会类传言。直接全量导入，检索会被大量无关条目稀释，
      而且答辩一问"你们知识库跟老人有什么关系"就答不上来。

做法：按四组关键词打分，保留命中至少一项的条目，另出一份 kb_elderly.json。
      官方条目一律保留（它们本来就少）。

用法：
    python tools/filter_elderly.py
    python tools/prep_kb.py kb_elderly.json      # 用子集生成导入包
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
KB_PATH = os.path.join(PROJ, "kb.json")
OUT_PATH = os.path.join(PROJ, "kb_elderly.json")

GROUPS = {
    "健康": ["老人", "老年", "养生", "保健", "降压", "降糖", "血糖", "血压", "三高", "癌",
             "药", "偏方", "秘方", "补钙", "骨头汤", "排毒", "中老年", "慢性病", "中风", "痴呆"],
    "养老与社保": ["养老", "退休", "社保", "医保", "养老金", "补贴", "公积金", "高龄", "护理",
                   "敬老", "老年大学", "社区养老", "长护险"],
    "诈骗": ["诈骗", "骗局", "转账", "汇款", "验证码", "公检法", "安全账户", "洗钱", "冒充",
             "免费领", "中奖", "投资", "理财", "保健品会销", "以房养老"],
    "政策": ["新规", "政策", "调整", "发放", "缴费", "报销", "待遇", "标准", "通知"],
}


def hits(text):
    got = {}
    for name, words in GROUPS.items():
        n = sum(1 for w in words if w in text)
        if n:
            got[name] = n
    return got


def main():
    with open(KB_PATH, encoding="utf-8") as f:
        kb = json.load(f)
    items = kb.get("items", [])

    kept, stat = [], {"官方保留": 0}
    for it in items:
        title = it.get("title", "")
        body = it.get("snippet", "")[:300]
        tier = it.get("tier", "dataset")
        g = hits(title + body)
        if tier == "official":
            kept.append(it)
            stat["官方保留"] += 1
            continue
        if g:
            kept.append(it)
            top = max(g, key=g.get)
            stat[top] = stat.get(top, 0) + 1

    out = dict(kb)
    out["items"] = kept
    out["note"] = "银龄相关子集，由 tools/filter_elderly.py 生成"
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    print("原始 %d 条 → 子集 %d 条（%.1f%%）" % (len(items), len(kept), len(kept) * 100.0 / max(len(items), 1)))
    print("构成：", stat)
    print("输出:", OUT_PATH)
    print("下一步: python tools/prep_kb.py kb_elderly.json")

    if len(kept) < 500:
        print("\n注意：子集不足 500 条。这个量足够演示，但覆盖会很窄，"
              "查不到的比例会偏高。要么接受并把'无据率'写进方案，要么补数据。")


if __name__ == "__main__":
    main()
