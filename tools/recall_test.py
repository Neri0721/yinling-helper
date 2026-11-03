# -*- coding: utf-8 -*-
"""
召回测试：给 20 条问题算 recall@1 / @3 / @5

为什么要有这个：知识库导进平台后，第一个要回答的问题是"它到底找得到吗"。
找不到，后面 Agent 编排做得再漂亮也是空转。

本脚本用字符二元组 + IDF 做一个轻量检索器，作为**基线**：
  - 它跑出来的数字，是平台向量检索要打赢的参照线；
  - 若平台召回比它还低，说明切分或元数据有问题，先修那个。

用法：
    python tools/recall_test.py            # 用 query_final，没填就用 query_draft
产物：
    tests/recall_report.md
"""

import array
import csv
import json
import math
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
DATA = os.path.join(HERE, "out", "kb_import.jsonl")
TESTSET = os.path.join(PROJ, "tests", "testset_20.csv")
REPORT = os.path.join(PROJ, "tests", "recall_report.md")

CLEAN = re.compile(r"[^\u4e00-\u9fa5A-Za-z0-9]")


def grams(text):
    s = CLEAN.sub("", (text or "").lower())
    return {s[i:i + 2] for i in range(len(s) - 1)}


def main():
    docs, ids, urls = [], [], []
    with open(DATA, encoding="utf-8") as f:
        for line in f:
            it = json.loads(line)
            docs.append(it["content"])
            ids.append(it["id"])
            urls.append(it["metadata"].get("url", ""))

    n = len(docs)
    print("索引文档数:", n)

    index = {}
    df = {}
    for i, text in enumerate(docs):
        g = grams(text)
        for gram in g:
            df[gram] = df.get(gram, 0) + 1
            index.setdefault(gram, array.array("i")).append(i)

    idf = {g: math.log((n + 1.0) / (c + 1.0)) + 1.0 for g, c in df.items()}
    print("词表规模:", len(index))

    rows = []
    with open(TESTSET, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            q = (r.get("query_final") or "").strip() or (r.get("query_draft") or "").strip()
            if q:
                rows.append((r, q))

    if not rows:
        print("测试集是空的，先跑 gen_testset.py")
        return

    hits = {1: 0, 3: 0, 5: 0}
    lines = ["# 召回测试报告（基线检索器）\n",
             "文档数 %d，测试问题 %d 条。\n" % (n, len(rows)),
             "| # | 领域 | 问题 | Top1 命中 | 命中名次 |",
             "|---|---|---|---|---|"]

    for k, (r, q) in enumerate(rows, 1):
        qg = grams(q)
        score = {}
        for g in qg:
            for d in index.get(g, ()):
                score[d] = score.get(d, 0.0) + idf.get(g, 1.0)
        ranked = sorted(score.items(), key=lambda x: -x[1])[:5]

        want_id, want_url = r["answer_id"], r["answer_url"]
        rank = None
        for pos, (d, _s) in enumerate(ranked, 1):
            if ids[d] == want_id or (want_url and urls[d] == want_url):
                rank = pos
                break
        top1 = docs[ranked[0][0]].split("\n")[0][:28] if ranked else "（无结果）"
        for kk in hits:
            if rank is not None and rank <= kk:
                hits[kk] += 1

        lines.append("| %d | %s | %s | %s | %s |" % (
            k, r["domain"], q[:26], top1,
            ("第 %d 位" % rank) if rank else "未命中"))

    total = len(rows)
    lines.append("")
    lines.append("## 结果\n")
    for kk in (1, 3, 5):
        lines.append("- recall@%d：%d / %d = **%.0f%%**" % (kk, hits[kk], total, hits[kk] * 100.0 / total))
    lines.append("")
    lines.append("## 怎么用这个数\n")
    lines.append("- recall@5 低于 60%：先别测平台，先修切分和标题质量。")
    lines.append("- 平台向量检索应该明显高于这个基线；如果没高，说明导入的字段顺序或元数据丢了。")
    lines.append("- 报告里\"未命中\"的条目，多半是口语与标题表达差异太大，把它们记下来，作为改写提示词的输入。")

    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print("recall@1 %d/%d" % (hits[1], total))
    print("recall@3 %d/%d" % (hits[3], total))
    print("recall@5 %d/%d" % (hits[5], total))
    print("报告:", REPORT)


if __name__ == "__main__":
    main()
