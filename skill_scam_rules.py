# -*- coding: utf-8 -*-
"""
银龄核查助手 · Skill 服务：scam_rules

用途：用规则识别老人高频受骗话术，输出四类：冒充公检法 / 保健品会销 /
      投资理财 / 补贴退税。只做初筛提示，不下最终真假结论。

启动：
    python skill_scam_rules.py          # 默认 8793
    python skill_scam_rules.py 9001

接口契约：
    POST /scam_rules
      {"text": "有人打电话说我的账户涉嫌洗钱，要转到安全账户"}
    → {"is_scam": true,
       "types": ["冒充公检法"],
       "risk": "高风险",
       "advice": "立即挂断..."}

    GET  /health → {"ok": true, "types": 4, "danger_words": 24}
    GET  /       → schema

复用：server.py 的 DANGER_WORDS；四类词表在本文件内维护，不改 server.py 常量。
"""

import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from server import DANGER_WORDS  # noqa: E402  复用主服务的危险词兜底表

MAX_TEXT = 2000

SCHEMA = {
    "skill": "scam_rules",
    "version": "1.0",
    "description": "识别四类老人高频诈骗话术。规则初筛，不是真假判决。",
    "input": {
        "type": "object",
        "properties": {"text": {"type": "string", "description": "待识别的话术，最长 2000 字"}},
        "required": ["text"],
    },
    "output": {
        "type": "object",
        "properties": {
            "is_scam": {"type": "boolean"},
            "types": {
                "type": "array",
                "items": {"type": "string",
                          "enum": ["冒充公检法", "保健品会销", "投资理财", "补贴退税"]},
            },
            "risk": {"type": "string", "enum": ["高风险", "中风险", "低风险"]},
            "advice": {"type": "string"},
        },
    },
    "limits": {"max_text_chars": MAX_TEXT, "timeout_ms": 500},
    "notes": "is_scam 表示命中典型话术，不等于已核实为骗局；未命中也可能是新骗法。",
}

# 每类：强信号命中 1 个即计入；弱信号需命中 2 个，降低误报。
RULES = {
    "冒充公检法": (
        ["公检法", "安全账户", "涉嫌", "洗钱", "通缉令", "拘捕", "逮捕令", "冻结账户",
         "办案民警", "警官证", "资金核查", "屏幕共享", "共享屏幕", "注销校园贷"],
        ["公安", "检察院", "法院", "警察", "涉案", "冻结", "保密", "不许告诉家人"],
    ),
    "保健品会销": (
        ["包治", "根治", "神药", "药到病除", "抗癌", "降血糖", "降血压", "停药",
         "会销", "免费领鸡蛋", "专家讲座", "健康讲座", "体验店", "祖传秘方", "偏方治大病"],
        ["保健品", "偏方", "秘方", "疗效", "专家", "赠送", "免费体验", "万元"],
    ),
    "投资理财": (
        ["稳赚", "保本高息", "高收益", "内幕消息", "原始股", "虚拟币", "刷单返利",
         "以房养老", "养老项目", "私募", "资金盘", "杀猪盘", "导师带单"],
        ["投资", "理财", "返利", "基金", "股票", "数字货币", "分红", "项目"],
    ),
    "补贴退税": (
        ["退税", "退费", "补贴发放", "养老金补发", "医保退费", "社保补贴",
         "个人所得税退税", "扫码领补贴", "领取补贴", "补贴到账"],
        ["补贴", "退税", "养老金", "社保", "医保", "发放", "领取", "政策"],
    ),
}

ADVICE = {
    "冒充公检法": "立即挂断，公检法不会电话办案、不会要验证码，也不会让你转到“安全账户”；拨打 96110 核实。",
    "保健品会销": "不要购买、不要交定金；先问医生或子女，保留宣传材料，必要时拨打 12315 举报。",
    "投资理财": "不要转账、不要下载陌生 App；高收益保本基本是骗局，先和子女商量并核实机构资质。",
    "补贴退税": "不要点陌生链接、不要扫码；通过人社、医保、税务官方渠道查询，或让子女陪同办理。",
}

GENERIC = "没发现典型诈骗话术，但涉及转账、验证码、陌生链接时仍要先停一下，找子女或拨打 96110 核实。"


def detect(text):
    text = text or ""
    types = []
    for name, (strong, weak) in RULES.items():
        if any(w in text for w in strong) or sum(1 for w in weak if w in text) >= 2:
            types.append(name)
    return types


def assess(text):
    types = detect(text)
    danger_hit = any(w in text for w in DANGER_WORDS)
    if len(types) >= 2 or (types and danger_hit):
        risk = "高风险"
    elif types:
        risk = "中风险"
    else:
        risk = "低风险"
    if types:
        advice = " ".join(ADVICE[t] for t in types)
        if danger_hit and "冒充公检法" not in types:
            advice += " 任何要转账、要验证码的要求都先拒绝。"
    else:
        advice = GENERIC
    return {
        "is_scam": bool(types),
        "types": types,
        "risk": risk,
        "advice": advice,
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stdout.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), fmt % args))

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/health"):
            return self._json(200, {
                "ok": True,
                "types": len(RULES),
                "danger_words": len(DANGER_WORDS),
            })
        return self._json(200, SCHEMA)

    def do_POST(self):
        if not self.path.startswith("/scam_rules"):
            return self._json(404, {"error": "not found"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if n > 1024 * 1024:
                return self._json(413, {"error": "payload too large"})
            payload = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        except Exception:
            return self._json(400, {"error": "bad json"})
        if not isinstance(payload, dict):
            return self._json(400, {"error": "bad json"})

        text = (payload.get("text") or "").strip()
        if not text:
            return self._json(400, {"error": "empty text"})
        if len(text) > MAX_TEXT:
            return self._json(400, {"error": "text too long, max %d chars" % MAX_TEXT})

        return self._json(200, assess(text))


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8793
    print("=" * 56)
    print("  scam_rules Skill")
    print("  类型: %d  危险词: %d" % (len(RULES), len(DANGER_WORDS)))
    print("  地址: http://127.0.0.1:%d/scam_rules" % port)
    print("=" * 56)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()