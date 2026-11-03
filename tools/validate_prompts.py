# -*- coding: utf-8 -*-
"""
提示词资产校验器（任务二）

两层校验：
  1. 静态层：prompts/*.md 是否包含 system prompt / few-shot / 输入输出 schema /
     golden example；所有 JSON 代码块能否解析；a2 的 no_evidence 硬约束是否存在。
  2. 结果层：吃外部 JSONL，每行 {"id","query","model_output"}，可选 "agent"。
     结构层校验字段/类型/枚举；业务层校验 evidence 与 verdict 的一致性。

用法：
    python tools/validate_prompts.py                       # 静态校验 + 内置 golden 冒烟
    python tools/validate_prompts.py --results out.jsonl   # 校验本地模型跑出的 20 条结果
    python tools/validate_prompts.py --results out.jsonl --agent a2

说明：本脚本不调用任何模型。报告中的结论仅为“结构校验通过”，不代表真实模型效果。
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
PROMPT_DIR = os.path.join(PROJ, "prompts")

FILES = {
    "a1": "a1_claim.md",
    "a2": "a2_verify.md",
    "a3": "a3_rewrite.md",
}
NAMES = {"a1": "a1_claim", "a2": "a2_verify", "a3": "a3_rewrite"}

INTENTS = ["verify", "advice", "share", "other"]
DOMAINS = ["健康", "钱财", "政策", "儿童", "其他"]
RISKS = ["高风险", "中风险", "暂无权威结论"]
VERDICTS = ["debunked", "supported", "insufficient", "no_evidence"]
TIERS = ["official", "dataset", "media"]

REQUIRED_SECTIONS = ["## System Prompt", "## Few-shot", "## 输入 JSON Schema",
                     "## 输出 JSON Schema", "## Golden example"]

LIMITS = {"conclusion": 30, "explanation": 80, "action_advice": 40,
          "voice_script": 120, "family_share_text": 100}

DEMO = [
    {"id": "demo-a1", "agent": "a1", "query": "喝骨头汤能补钙吗",
     "model_output": {"intent": "verify", "claim": "喝骨头汤能补钙并预防骨质疏松",
                      "domain": "健康", "need_clarify": False}},
    {"id": "demo-a2", "agent": "a2", "query": "喝骨头汤能补钙吗",
     "model_output": {"risk_level": "高风险", "verdict": "debunked",
                      "evidence": {"tier": "official",
                                   "url": "https://www.piyao.org.cn/2026xxxx/c.html",
                                   "source_name": "中国互联网联合辟谣平台",
                                   "date": "2026-10",
                                   "snippet": "骨头汤里的钙含量并不高。"}}},
    {"id": "demo-a2-empty", "agent": "a2", "query": "2027 年统一补发 800 元",
     "model_output": {"risk_level": "暂无权威结论", "verdict": "no_evidence",
                      "evidence": None}},
    {"id": "demo-a3", "agent": "a3", "query": "喝骨头汤能补钙吗",
     "model_output": {"conclusion": "这是谣言，骨头汤补钙不靠谱",
                      "explanation": "骨头汤里钙很少，喝多了还容易油大。",
                      "action_advice": "别信偏方，缺钙去问医生。",
                      "voice_script": "这是谣言。骨头汤里钙很少，靠它补钙不靠谱。",
                      "family_share_text": "核查结论：骨头汤补钙是谣言。别转发。"}},
]

STRUCT_ERRORS = []
BUSINESS_ERRORS = []


def fail(bucket, item, msg):
    bucket.append((item, msg))


def infer_agent(out, hint=None):
    if hint:
        h = str(hint).lower()
        if h.startswith("a1"):
            return "a1"
        if h.startswith("a2"):
            return "a2"
        if h.startswith("a3"):
            return "a3"
    if not isinstance(out, dict):
        return None
    if "intent" in out:
        return "a1"
    if "verdict" in out:
        return "a2"
    if "voice_script" in out:
        return "a3"
    return None


def check_structure(agent, out):
    errs = []
    if not isinstance(out, dict):
        return ["model_output 不是 JSON 对象"]
    if agent == "a1":
        for k in ("intent", "claim", "domain", "need_clarify"):
            if k not in out:
                errs.append("缺少字段 %s" % k)
        if out.get("intent") not in INTENTS and "intent" in out:
            errs.append("intent 不在枚举内：%r" % out.get("intent"))
        if out.get("domain") not in DOMAINS and "domain" in out:
            errs.append("domain 不在枚举内：%r" % out.get("domain"))
        if "claim" in out and not isinstance(out.get("claim"), str):
            errs.append("claim 必须是字符串")
        if "need_clarify" in out and not isinstance(out.get("need_clarify"), bool):
            errs.append("need_clarify 必须是布尔值")
    elif agent == "a2":
        for k in ("risk_level", "verdict", "evidence"):
            if k not in out:
                errs.append("缺少字段 %s" % k)
        if out.get("risk_level") not in RISKS and "risk_level" in out:
            errs.append("risk_level 不在枚举内：%r" % out.get("risk_level"))
        if out.get("verdict") not in VERDICTS and "verdict" in out:
            errs.append("verdict 不在枚举内：%r" % out.get("verdict"))
        ev = out.get("evidence")
        if ev is not None:
            if not isinstance(ev, dict):
                errs.append("evidence 必须是对象或 null")
            else:
                for k in ("tier", "url", "source_name", "date", "snippet"):
                    if k not in ev:
                        errs.append("evidence 缺少字段 %s" % k)
                    elif not isinstance(ev.get(k), str):
                        errs.append("evidence.%s 必须是字符串" % k)
                if ev.get("tier") not in TIERS and "tier" in ev:
                    errs.append("evidence.tier 不在枚举内：%r" % ev.get("tier"))
    elif agent == "a3":
        for k in LIMITS:
            if k not in out:
                errs.append("缺少字段 %s" % k)
            elif not isinstance(out.get(k), str):
                errs.append("%s 必须是字符串" % k)
    elif agent is None:
        errs.append("无法识别 agent（缺少 intent/verdict/voice_script）")
    return errs


def evidence_empty(ev):
    if ev is None or ev == {}:
        return True
    if not isinstance(ev, dict):
        return True
    return not any(str(ev.get(k) or "").strip()
                   for k in ("tier", "url", "source_name", "date", "snippet"))


def check_business(agent, out, ctx=None):
    errs = []
    if not isinstance(out, dict):
        return errs
    if agent == "a1":
        if out.get("need_clarify") is False and not (out.get("claim") or "").strip():
            errs.append("need_clarify=false 时 claim 不能为空")
        if out.get("need_clarify") is True and out.get("intent") not in ("other", "verify", "advice", "share"):
            errs.append("need_clarify=true 时 intent 仍须是合法枚举")
    elif agent == "a2":
        ev = out.get("evidence")
        verdict = out.get("verdict")
        risk = out.get("risk_level")
        if evidence_empty(ev):
            if verdict != "no_evidence":
                errs.append("evidence 为空但 verdict=%r，必须是 no_evidence" % verdict)
            if risk != "暂无权威结论":
                errs.append("evidence 为空但 risk_level=%r，必须是 暂无权威结论" % risk)
        else:
            if verdict == "no_evidence":
                errs.append("evidence 非空但 verdict=no_evidence")
            if isinstance(ev, dict) and ev.get("tier") == "dataset" and risk == "高风险":
                errs.append("dataset 证据不得判高风险")
            for k in ("source_name", "date", "snippet"):
                if isinstance(ev, dict) and not str(ev.get(k) or "").strip():
                    errs.append("evidence.%s 为空，不得编造或留空" % k)
            if isinstance(ev, dict) and ev.get("tier") in ("official", "media") \
                    and not str(ev.get("url") or "").strip():
                errs.append("official/media 证据必须带 url")
    elif agent == "a3":
        for k, n in LIMITS.items():
            v = out.get(k)
            if isinstance(v, str) and len(v) > n:
                errs.append("%s 超长：%d > %d" % (k, len(v), n))
        verdict = None
        if isinstance(ctx, dict):
            verdict = ctx.get("verdict")
        if verdict == "no_evidence":
            c = out.get("conclusion") or ""
            if any(w in c for w in ("这是谣言", "这是真的", "是骗局", "肯定真", "肯定假")):
                errs.append("verdict=no_evidence 时 conclusion 不得下绝对结论")
    return errs


def json_blocks(text):
    return re.findall(r"```json\s*(.*?)```", text, re.S)


def check_prompt_files():
    ok_all = True
    for agent, fname in FILES.items():
        path = os.path.join(PROMPT_DIR, fname)
        if not os.path.exists(path):
            print("[FAIL] %s 不存在" % fname)
            ok_all = False
            continue
        text = open(path, encoding="utf-8").read()
        missing = [s for s in REQUIRED_SECTIONS if s not in text]
        blocks = json_blocks(text)
        bad = []
        for i, b in enumerate(blocks, 1):
            try:
                json.loads(b)
            except Exception as e:
                bad.append("第 %d 个 JSON 块：%s" % (i, str(e)[:80]))
        if missing or bad or not blocks:
            print("[FAIL] prompts/%s 结构不完整%s%s" % (
                fname, ("；缺少：" + "、".join(missing)) if missing else "",
                ("；" + "；".join(bad)) if bad else ""))
            ok_all = False
        else:
            print("[PASS] prompts/%s 结构完整（%d 个 JSON 块）" % (fname, len(blocks)))

    a2 = os.path.join(PROMPT_DIR, FILES["a2"])
    if os.path.exists(a2):
        text = open(a2, encoding="utf-8").read()
        need = ["evidence 为空时", "verdict 必须是 no_evidence"]
        miss = [n for n in need if n not in text]
        if miss:
            print("[FAIL] a2_verify.md 硬约束缺失：%s" % "、".join(miss))
            ok_all = False
        else:
            print("[PASS] a2_verify.md 硬约束：evidence 为空时 verdict 必须是 no_evidence")

    golden_path = os.path.join(PROMPT_DIR, FILES["a2"])
    if os.path.exists(golden_path):
        text = open(golden_path, encoding="utf-8").read()
        m = re.search(r"## Golden example\s*```json\s*(.*?)```", text, re.S)
        if m:
            try:
                out = json.loads(m.group(1))
                errs = check_structure("a2", out) + check_business("a2", out)
                if errs:
                    print("[FAIL] a2 golden example：%s" % "；".join(errs))
                    ok_all = False
                else:
                    print("[PASS] a2 golden example 可解析且符合 schema")
            except Exception as e:
                print("[FAIL] a2 golden example 解析失败：%s" % str(e)[:80])
                ok_all = False
    return ok_all


def validate_records(records, only_agent=None):
    n = 0
    struct_pass = 0
    biz_pass = 0
    for idx, rec in enumerate(records, 1):
        if not isinstance(rec, dict):
            fail(STRUCT_ERRORS, idx, "不是 JSON 对象")
            continue
        out = rec.get("model_output")
        if isinstance(out, str):
            try:
                out = json.loads(out)
            except Exception as e:
                fail(STRUCT_ERRORS, idx, "model_output JSON 解析失败：%s" % str(e)[:80])
                continue
        agent = infer_agent(out, rec.get("agent"))
        if only_agent and agent != only_agent:
            continue
        n += 1
        rid = rec.get("id", idx)
        ctx = rec.get("input") if isinstance(rec.get("input"), dict) else None
        errs = check_structure(agent, out)
        if errs:
            fail(STRUCT_ERRORS, rid, "；".join(errs))
            print("[FAIL] #%s %s 结构：%s" % (rid, NAMES.get(agent, "?"), "；".join(errs)))
        else:
            struct_pass += 1
            print("[PASS] #%s %s 结构" % (rid, NAMES.get(agent, "?")))
        if agent:
            errs = check_business(agent, out, ctx)
            if errs:
                fail(BUSINESS_ERRORS, rid, "；".join(errs))
                print("[FAIL] #%s %s 业务：%s" % (rid, NAMES.get(agent, "?"), "；".join(errs)))
            else:
                biz_pass += 1
                print("[PASS] #%s %s 业务" % (rid, NAMES.get(agent, "?")))
    return n, struct_pass, biz_pass


def load_jsonl(path):
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def main():
    args = sys.argv[1:]
    results = None
    only_agent = None
    if "--results" in args:
        results = args[args.index("--results") + 1]
    if "--agent" in args:
        only_agent = args[args.index("--agent") + 1].lower()

    print("=" * 60)
    print("  提示词资产校验")
    print("=" * 60)
    ok = check_prompt_files()

    if results:
        try:
            records = load_jsonl(results)
        except Exception as e:
            print("[FAIL] 读取 JSONL 失败：%s" % str(e)[:120])
            print("RESULT: FAIL")
            return 1
        print("-" * 60)
        print("外部结果：%s（%d 行）" % (results, len(records)))
    else:
        records = DEMO

    n, sp, bp = validate_records(records, only_agent=only_agent)
    print("-" * 60)
    print("结构层：%d/%d 通过；业务层：%d/%d 通过" % (sp, n, bp, n))

    if not results:
        print("说明：当前为内置 golden example 冒烟，未接真实模型。")
    print("未接真实模型，仅结构校验通过。")

    failed = bool(STRUCT_ERRORS or BUSINESS_ERRORS) or not ok or sp != n or bp != n
    print("RESULT: %s" % ("FAIL" if failed else "PASS"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())