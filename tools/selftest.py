# -*- coding: utf-8 -*-
"""
一键自测：编译 → 起服务 → 健康/文字/图片 → 召回基线 → PASS/FAIL

用法：
    python tools/selftest.py
    python tools/selftest.py --port 8877

约定：
  - 默认带 OFFLINE=1 启动，禁用 live_search，保证结果可复现；
  - OCR 固定用 mock，图片链路只验证"能走通"，不验证识别准确率；
  - 知识库必须加载到条目（kb_items > 0），否则 FAIL——空库跑出来的绿是假绿；
  - 召回基线为子集口径（3,188 块），数字来自 2026-11-03 实测。
"""

import base64
import csv
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
PY = sys.executable
PORT = 8877
BASE_URL = "http://127.0.0.1:%d" % PORT

# 子集口径实测基线（tests/recall_report.md）
BASELINE = {1: 17, 3: 18, 5: 18}

PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9ZlS8AAAAASUVORK5CYII="
)

RESULTS = []


def record(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print("[%s] %s%s" % ("PASS" if ok else "FAIL", name, (" — " + detail) if detail else ""))
    return ok


def http_json(base, method, path, payload=None, timeout=40):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read().decode("utf-8")
        return r.status, json.loads(body)


def wait_health(proc, base, seconds=30, path="/health"):
    deadline = time.time() + seconds
    last = ""
    while time.time() < deadline:
        if proc.poll() is not None:
            return None, "服务进程已退出（code=%s）" % proc.returncode
        try:
            code, data = http_json(base, "GET", path, timeout=4)
            if code == 200:
                return data, ""
            last = "HTTP %s" % code
        except Exception as e:
            last = str(e)[:80]
        time.sleep(0.4)
    return None, "健康检查超时：%s" % last


def compile_all():
    files = []
    for root, dirs, names in os.walk(PROJ):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "out", ".codeartsdoer")]
        for n in names:
            if n.endswith(".py"):
                files.append(os.path.join(root, n))
    bad = []
    for p in sorted(files):
        r = subprocess.run([PY, "-m", "py_compile", p], capture_output=True, text=True)
        if r.returncode != 0:
            bad.append("%s: %s" % (os.path.relpath(p, PROJ), (r.stderr or "").strip()[:200]))
    record("py_compile 全部 .py（%d 个）" % len(files), not bad, "；".join(bad))
    return not bad


def first_query():
    path = os.path.join(PROJ, "tests", "testset_20.csv")
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            q = (row.get("query_final") or "").strip() or (row.get("query_draft") or "").strip()
            if q:
                return q
    return "喝骨头汤能补钙是真的吗"


def test_service():
    env = os.environ.copy()
    env["OFFLINE"] = "1"
    env["OCR_PROVIDER"] = "mock"
    proc = subprocess.Popen(
        [PY, "server.py", str(PORT)],
        cwd=PROJ, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        health, err = wait_health(proc, BASE_URL, path="/api/health")
        ok_health = record(
            "GET /api/health",
            bool(health and health.get("ok")),
            err or ("kb_source=%s kb_items=%s offline=%s" % (
                (health or {}).get("kb_source"), (health or {}).get("kb_items"),
                (health or {}).get("offline"))),
        )
        kb_ok = record(
            "知识库非空（kb_items > 0）",
            bool(health and int(health.get("kb_items") or 0) > 0),
            "kb_source=%s kb_items=%s" % (
                (health or {}).get("kb_source"), (health or {}).get("kb_items")),
        )

        text = first_query()
        try:
            code, card = http_json(BASE_URL, "POST", "/api/check", {"text": text})
            text_ok = record(
                "POST /api/check 文字一条",
                code == 200 and card.get("type") == "card"
                and card.get("verdict") == "evidence_found"
                and card.get("risk_level"),
                "type=%s verdict=%s tier=%s risk=%s" % (
                    card.get("type"), card.get("verdict"),
                    card.get("source_tier"), card.get("risk_level")),
            )
        except Exception as e:
            text_ok = record("POST /api/check 文字一条", False, str(e)[:120])

        try:
            code, card = http_json(BASE_URL, "POST", "/api/check", {
                "image": base64.b64encode(PNG_1PX).decode("ascii"),
            })
            img_ok = record(
                "POST /api/check 图片一条（mock OCR）",
                code == 200 and card.get("type") == "card"
                and bool(card.get("ocr_text")) and card.get("ocr_provider") == "mock",
                "type=%s provider=%s ocr_text=%s" % (
                    card.get("type"), card.get("ocr_provider"),
                    (card.get("ocr_text") or "")[:24]),
            )
        except Exception as e:
            img_ok = record("POST /api/check 图片一条（mock OCR）", False, str(e)[:120])

        try:
            req = urllib.request.Request(
                BASE_URL + "/api/proxy",
                data=b'{"text":"hi"}',
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=10) as r:
                    code, pr = r.status, json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                code, pr = e.code, json.loads(e.read().decode("utf-8"))
            proxy_ok = record(
                "POST /api/proxy 未配置提示",
                code == 503 and pr.get("type") == "not_configured",
                "HTTP %s type=%s" % (code, pr.get("type")),
            )
        except Exception as e:
            proxy_ok = record("POST /api/proxy 未配置提示", False, str(e)[:120])
    finally:
        _stop(proc)
    return ok_health and kb_ok and text_ok and img_ok and proxy_ok


def _start_skill(script, port, env):
    return subprocess.Popen(
        [PY, script, str(port)], cwd=PROJ, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )


def _stop(proc):
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def test_skills():
    env = os.environ.copy()
    env["OFFLINE"] = "1"
    env["OCR_PROVIDER"] = "mock"
    cases = [
        ("kb_search", "skill_kb_search.py", 8891, "/kb_search",
         {"query": first_query(), "top_k": 2},
         lambda d: bool(d.get("hits")), "total=%d"),
        ("source_verify", "skill_source_verify.py", 8892, "/source_verify",
         {"url": "https://example.com/not-authoritative"},
         lambda d: d.get("official") is False and d.get("tier") == "dataset",
         "official=%s tier=%s error=%s"),
        ("scam_rules", "skill_scam_rules.py", 8893, "/scam_rules",
         {"text": "有人打电话说我的账户涉嫌洗钱，要把钱转到安全账户，还要了验证码"},
         lambda d: bool(d.get("is_scam")) and "冒充公检法" in (d.get("types") or []),
         "is_scam=%s types=%s risk=%s"),
    ]
    ok_all = True
    for name, script, port, path, payload, predicate, fmt in cases:
        base = "http://127.0.0.1:%d" % port
        proc = _start_skill(script, port, env)
        try:
            health, err = wait_health(proc, base, seconds=20)
            if not (health and health.get("ok")):
                ok_all = record("Skill %s GET /health" % name, False, err or str(health))
                continue
            try:
                code, data = http_json(base, "POST", path, payload, timeout=25)
                detail = fmt % tuple(data.get(k) for k in _fields(fmt))
                ok_all = record("Skill %s POST %s" % (name, path),
                                code == 200 and predicate(data), detail) and ok_all
            except Exception as e:
                ok_all = record("Skill %s POST %s" % (name, path), False, str(e)[:120]) and ok_all
        finally:
            _stop(proc)
    return ok_all


def _fields(fmt):
    return re.findall(r"(\w+)=%[sd]", fmt)


def test_prompts():
    script = os.path.join(HERE, "validate_prompts.py")
    r = subprocess.run([PY, script], cwd=PROJ, capture_output=True, text=True)
    out = (r.stdout or "") + (r.stderr or "")
    ok = r.returncode == 0 and "RESULT: PASS" in out
    tail = [ln for ln in out.splitlines() if "结构层" in ln or "未接真实模型" in ln]
    return record("prompts 静态校验（未接真实模型）", ok,
                  "；".join(tail) if ok else out.strip()[-200:])


def test_mobile():
    path = os.path.join(PROJ, "mobile.html")
    if not os.path.exists(path):
        return record("mobile.html 首屏检查", False, "文件不存在")
    text = open(path, encoding="utf-8").read()
    problems = []
    for needle in ('id="btnPhoto"', 'id="btnTalk"', 'id="talkInput"', 'id="btnAgain"'):
        if needle not in text:
            problems.append("缺少 " + needle)
    if 'class="composer"' in text:
        problems.append("首屏仍保留底部输入区")
    ext = re.findall(r"https?://[^\s\"'<>]+", text)
    if ext:
        problems.append("存在外部资源：%s" % "、".join(ext[:3]))
    total = 0
    for name in ("mobile.html", "manifest.webmanifest", "sw.js", "icon-192.png"):
        p = os.path.join(PROJ, name)
        if os.path.exists(p):
            total += os.path.getsize(p)
    if total > 200 * 1024:
        problems.append("首屏资源 %d 字节，超过 200 KB" % total)
    return record("mobile.html 首屏检查", not problems,
                  "；".join(problems) if problems else "双入口齐全，首屏资源 %.1f KB，无外链" % (total / 1024.0))


def test_recall():
    r = subprocess.run([PY, os.path.join(HERE, "recall_test.py")],
                       cwd=PROJ, capture_output=True, text=True)
    out = (r.stdout or "") + (r.stderr or "")
    print(out.strip())
    got = {}
    for k in (1, 3, 5):
        m = re.search(r"recall@%d\s+(\d+)/(\d+)" % k, out)
        if m:
            got[k] = (int(m.group(1)), int(m.group(2)))
    ok = r.returncode == 0 and all(k in got for k in (1, 3, 5))
    detail = " ".join("recall@%d=%s/%s" % (k, got[k][0], got[k][1]) for k in (1, 3, 5) if k in got)
    if not ok:
        detail = detail or (out.strip()[-200:] or "未拿到 recall 结果")
        return record("recall 子集基线", False, detail)
    for k in (1, 3, 5):
        if got[k][0] < BASELINE[k]:
            return record("recall 子集基线", False, "%s，低于基线 @%d=%d" % (detail, k, BASELINE[k]))
    return record("recall 子集基线", True, detail + "（基线 @1=17 @3=18 @5=18）")


def main():
    global PORT, BASE_URL
    if "--port" in sys.argv:
        PORT = int(sys.argv[sys.argv.index("--port") + 1])
        BASE_URL = "http://127.0.0.1:%d" % PORT

    print("=" * 60)
    print("  银龄核查助手 · 一键自测")
    print("  Python: %s" % PY)
    print("=" * 60)

    compile_all()
    test_service()
    test_skills()
    test_prompts()
    test_mobile()
    test_recall()

    failed = [n for n, ok, _d in RESULTS if not ok]
    print("=" * 60)
    print("汇总：%d 项，通过 %d，失败 %d" % (len(RESULTS), len(RESULTS) - len(failed), len(failed)))
    if failed:
        print("FAIL: " + "；".join(failed))
        print("RESULT: FAIL")
        return 1
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())