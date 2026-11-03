# -*- coding: utf-8 -*-
"""
生成 20 条召回测试集

做法：按领域分层抽 20 条（健康/钱财/政策/儿童各 5 条），
      优先取 official 条目，某个领域不够就用同领域的平台辟谣语料补，
      保证一定是 20 条。
      用标题反推一句"老人可能怎么问"作草稿，四种问法轮换。

注意：这份草稿是"开卷"的——它是标题的改写，所以基线召回会偏高。
      你们把 query_final 改写成真正的口语（"我妈在群里看到……"）之后重跑，
      那个数字才算数。

产物：tests/testset_20.csv
  id / domain / query_draft / query_final（可留空）/ answer_id / answer_title / answer_url / notes

用法：
    python tools/gen_testset.py
"""

import csv
import json
import os
import random
import re

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
DATA = os.path.join(HERE, "out", "kb_import_elderly.jsonl")
TEST_DIR = os.path.join(PROJ, "tests")

PER_DOMAIN = 5
DOMAINS = ["健康", "钱财", "政策", "儿童"]
random.seed(42)

QUOTED = re.compile(r"[“\"「]([^”\"」]{6,30})[”\"」]")

TEMPLATES = [
    "听说%s，是真的吗",
    "群里有人发%s，能信吗",
    "我妈说%s，我要不要信",
    "网上说%s，这靠谱吗",
]


def core_of(title):
    """从标题里抠出可核查的那句话"""
    t = re.sub(r"^[^丨|\s]{2,8}[丨|]\s*", "", title)   # 去掉"晓真播报丨"这类栏目前缀
    m = QUOTED.search(t)
    if m:
        core = m.group(1)
    else:
        core = re.sub(r"^(网传|听说|注意|警惕|紧急|辟谣|今日辟谣)", "", t)
        core = re.split(r"[？?！!]", core)[0]
        core = re.sub(r"(官方回应|真相是|别再信|假的|不实|回应来了).*$", "", core)
    core = core.strip(" ，。、：:")
    return core if len(core) >= 6 else ""


def main():
    os.makedirs(TEST_DIR, exist_ok=True)
    items = []
    with open(DATA, encoding="utf-8") as f:
        for line in f:
            items.append(json.loads(line))

    def usable(it):
        if not (30 <= len(it["content"]) <= 400):
            return False
        if not core_of(it["title"]):
            return False
        # 一条里塞三四条谣言的"合集页"，一个问题对应不了，跳过
        if it["title"].count("？") + it["title"].count("?") > 1:
            return False
        return True

    pools = {"official": {}, "dataset": {}}
    for it in items:
        m = it["metadata"]
        if not usable(it):
            continue
        g = "official" if m["tier"] == "official" else "dataset"
        pools[g].setdefault(m["domain"], []).append(it)

    for g in pools:
        for d in pools[g]:
            random.shuffle(pools[g][d])

    picked_by_domain = {}
    for dom in DOMAINS:
        got = []
        seen = set()
        for g in ("official", "dataset"):
            for it in pools[g].get(dom, []):
                if len(got) >= PER_DOMAIN:
                    break
                if it["title"] in seen:
                    continue
                seen.add(it["title"])
                got.append((it, g))
        picked_by_domain[dom] = got

    # 某个领域实在不够，从其余条目里补，保证总数 20
    total = sum(len(v) for v in picked_by_domain.values())
    if total < 20:
        used = {it["id"] for v in picked_by_domain.values() for it, _g in v}
        for it in items:
            if total >= 20:
                break
            if it["id"] in used or not usable(it):
                continue
            dom = it["metadata"]["domain"]
            g = "official" if it["metadata"]["tier"] == "official" else "dataset"
            picked_by_domain.setdefault(dom, []).append((it, g))
            used.add(it["id"])
            total += 1

    rows, n = [], 0
    for dom in list(picked_by_domain.keys()):
        for it, g in picked_by_domain[dom]:
            n += 1
            q = TEMPLATES[(n - 1) % len(TEMPLATES)] % core_of(it["title"])
            note = "官方条目" if g == "official" else "平台辟谣语料"
            rows.append([it["id"], it["metadata"]["domain"], q, "",
                         it["id"], it["title"], it["metadata"]["url"], note])

    out = os.path.join(TEST_DIR, "testset_20.csv")
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "domain", "query_draft", "query_final",
                    "answer_id", "answer_title", "answer_url", "notes"])
        w.writerows(rows)

    dist, src = {}, {}
    for r in rows:
        dist[r[1]] = dist.get(r[1], 0) + 1
        src[r[7]] = src.get(r[7], 0) + 1
    print("生成 %d 条：%s" % (len(rows), dist))
    print("来源：", src)
    print("输出:", out)


if __name__ == "__main__":
    main()
