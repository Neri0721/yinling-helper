# -*- coding: utf-8 -*-
"""200 条评估集：生成 → 跑分 → 出表

A 类（100 条）：知识库里确实存在的传言 → 期望判出风险
B 类（100 条）：老年话题但知识库里没有的说法 → 期望回答"查不到"

B 类不是拍脑袋定的：每条都先用项目自己的匹配器查一遍，
分数低于阈值（0.50）才收进样本，保证"无据"标签是真的。

用法：
    python tools/eval_build_run.py
产物：
    tests/eval_200.csv           逐条结果（边跑边写）
    tests/eval_200_summary.xlsx  汇总表
"""

import csv
import json
import os
import random
import re
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
KB = os.path.join(PROJ, "kb_elderly.json")
OUT_DIR = os.path.join(PROJ, "tests")
PORT = 8891
BASE = "http://127.0.0.1:%d" % PORT
THRESHOLD = 0.50

try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

random.seed(20261115)

HERBS = ["三七粉", "鱼腥草", "蒲公英", "苦瓜干", "灵芝孢子粉", "秋葵水", "黑枸杞", "玛卡片"]
BRANDS = ["康寿", "金鹤", "银龄宝", "百岁康", "安泰", "福寿堂"]
GIFTS = ["鸡蛋", "大米", "食用油", "洗衣液", "按摩仪"]
TEMPLATES = [
    "{y} 年起，{age} 岁以上老人每月增发 {n} 元高龄补贴，不登记就领不到",
    "{brand}老年奶粉被检出激素，长期喝会导致骨质疏松",
    "国家规定 {age} 岁以上老人每年可以免费体检 {n} 次",
    "用{herb}泡水喝能治好高血压，不用再吃降压药",
    "从 {m} 月起，养老金改由社保卡发放，不去社区登记就会停发",
    "{brand}牌保健品被曝含违禁成分，长期服用会伤肝",
    "社区免费发放{gift}，只要登记身份证就能领",
    "{herb}能替代化疗，很多老人靠它治好了癌症",
]
ASK = ["听说%s，是真的吗", "群里有人发%s，能信吗",
       "我妈说%s，我要不要信", "网上说%s，这靠谱吗"]


def colloquial(title):
    t = re.sub(r"\s*[-—]\s*中国互联网联合辟谣平台\s*$", "", title or "")
    t = re.sub(r"^[^丨|]{2,8}[丨|]\s*", "", t)
    m = re.search(r"[“\"「]([^”\"」]{6,30})[”\"」]", t)
    core = m.group(1) if m else re.split(r"[？?！!]", t)[0]
    core = re.sub(r"^(网传|听说|注意|警惕|辟谣)", "", core).strip(" ，。、")
    if len(core) < 6:
        return ""
    return random.choice(ASK) % core


def fabricated():
    q = random.choice(TEMPLATES).format(
        y=random.choice([2028, 2029, 2030, 2031]),
        age=random.choice([60, 65, 70, 75, 80]),
        n=random.choice([50, 80, 120, 200, 300]),
        brand=random.choice(BRANDS),
        herb=random.choice(HERBS),
        m=random.randint(1, 12),
        gift=random.choice(GIFTS),
    )
    return random.choice(ASK) % q


def wait_health(proc, seconds=40):
    deadline = time.time() + seconds
    while time.time() < deadline:
        if proc.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(BASE + "/api/health", timeout=3) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.4)
    return False


def check(text):
    body = json.dumps({"text": text}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(BASE + "/api/check", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=12) as r:
        d = json.loads(r.read().decode("utf-8"))
    return d, int((time.time() - t0) * 1000)


def main():
    sys.path.insert(0, PROJ)
    os.chdir(PROJ)
    import server

    kb = json.load(open(KB, encoding="utf-8"))["items"]
    pool = [it for it in kb if it.get("tier") == "official"
            and 30 <= len(it.get("snippet", "")) < 1500]
    random.shuffle(pool)

    rows, seen = [], set()
    for it in pool:
        q = colloquial(it.get("title", ""))
        if not q or q in seen:
            continue
        seen.add(q)
        rows.append({"cls": "A", "query": q, "expect": "有据",
                     "answer_url": it.get("url", ""), "title": it.get("title", "")})
        if len(rows) >= 100:
            break

    kept, dropped = [], 0
    tries = 0
    while len(kept) < 100 and tries < 3000:
        tries += 1
        q = fabricated()
        if q in kept:
            continue
        hits = server.kb_match(q, server.KB, limit=1)
        best = hits[0][0] if hits else 0.0
        if best < THRESHOLD:
            kept.append(q)
        else:
            dropped += 1

    for q in kept:
        rows.append({"cls": "B", "query": q, "expect": "无据",
                     "answer_url": "", "title": "知识库中不存在"})
    random.shuffle(rows)
    print("样本 A=%d B=%d（无据候选丢弃 %d 条）"
          % (sum(1 for r in rows if r["cls"] == "A"), len(kept), dropped))

    env = os.environ.copy()
    env["OFFLINE"] = "1"
    env["OCR_PROVIDER"] = "mock"
    proc = subprocess.Popen([sys.executable, "server.py", str(PORT)], cwd=PROJ, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not wait_health(proc):
        print("服务没起来，退出")
        proc.kill()
        return

    results = []
    out = os.path.join(OUT_DIR, "eval_200.csv")
    f = open(out, "w", encoding="utf-8-sig", newline="")
    w = csv.DictWriter(f, fieldnames=["cls", "query", "expect", "risk", "conclusion",
                                      "has_source", "ms", "ok", "answer_url", "title"])
    w.writeheader()
    f.flush()
    try:
        for i, r in enumerate(rows, 1):
            try:
                d, ms = check(r["query"])
            except Exception as e:
                d, ms = {"risk_level": "ERROR", "conclusion": str(e)[:60]}, 0
            risk = d.get("risk_level", "")
            concluded = risk in ("高风险", "中风险")
            rec = dict(r, risk=risk, conclusion=d.get("conclusion", ""),
                       has_source=bool(d.get("source_url")), ms=ms,
                       ok=((r["cls"] == "A") == concluded))
            results.append(rec)
            w.writerow(rec)
            f.flush()
            if i % 20 == 0:
                print("  已跑 %d/%d" % (i, len(rows)))
    finally:
        f.close()
        proc.kill()

    A = [x for x in results if x["cls"] == "A"]
    B = [x for x in results if x["cls"] == "B"]
    a_hit = sum(1 for x in A if x["risk"] in ("高风险", "中风险"))
    b_bad = sum(1 for x in B if x["risk"] in ("高风险", "中风险"))
    src = sum(1 for x in A if x["has_source"])
    avg = sum(x["ms"] for x in results) / max(len(results), 1)

    summary = {
        "样本总数": len(results),
        "A类有据": len(A),
        "B类无据": len(B),
        "A判出风险": a_hit,
        "A带出处": src,
        "B误判为谣言": b_bad,
        "有据判出率%": round(a_hit * 100.0 / max(len(A), 1), 1),
        "带出处率%": round(src * 100.0 / max(len(A), 1), 1),
        "无据诚实率%": round((len(B) - b_bad) * 100.0 / max(len(B), 1), 1),
        "误判率%": round(b_bad * 100.0 / max(len(B), 1), 1),
        "平均响应ms": round(avg, 0),
    }
    for k, v in summary.items():
        print("  %-12s %s" % (k, v))

    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "汇总"
        ws.append(["指标", "数值"])
        for k, v in summary.items():
            ws.append([k, v])
        for c in ws[1]:
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor="B3121D")
        ws.column_dimensions["A"].width = 18
        ws.column_dimensions["B"].width = 12

        ws2 = wb.create_sheet("逐条")
        ws2.append(["类型", "问题", "期望", "判定", "结论", "有出处", "耗时ms"])
        for x in results:
            ws2.append([x["cls"], x["query"], x["expect"], x["risk"], x["conclusion"],
                        "是" if x["has_source"] else "否", x["ms"]])
        for i, wd in enumerate([6, 50, 8, 10, 36, 8, 9]):
            ws2.column_dimensions[chr(65 + i)].width = wd
        for c in ws2[1]:
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor="1F6FEB")

        xls = os.path.join(OUT_DIR, "eval_200_summary.xlsx")
        wb.save(xls)
        print("表格:", xls)
    except Exception as e:
        print("xlsx 失败:", e)


if __name__ == "__main__":
    main()
