"""
银龄核查助手 · Skill 服务：ocr_extract

用途：把"拍照识图"这一步单独暴露成一个 HTTP 能力，方便在华为云 AgentArts
      里包装成插件 / MCP 工具挂到 Agent 上，而不是把 OCR 写死在主服务里。

启动：
    python skill_ocr.py           # 默认 8790
    python skill_ocr.py 9001

接口契约（AgentArts 侧按此定义入参出参）：
    POST /ocr_extract
      {"image_base64": "<不带 data: 前缀的 base64>", "mime": "image/jpeg"}
    → {"text": "...", "lines": ["..."], "provider": "huaweicloud",
       "ms": 812, "chars": 46, "error": null}

    GET  /health   → {"ok": true, "provider": "...", "provider_label": "..."}
    GET  /         → 本文件开头那段 schema（方便直接贴进平台文档）

注：与主服务一致，不落盘、不打日志正文、返回前打码。
"""

import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import ocr

MAX_BYTES = 8 * 1024 * 1024

SCHEMA = {
    "skill": "ocr_extract",
    "version": "1.0",
    "description": "把一张照片或截图转成文字，供核查链路使用。只做识别，不判断真伪。",
    "input": {
        "type": "object",
        "properties": {
            "image_base64": {"type": "string", "description": "图片 base64，不带 data: 前缀"},
            "mime": {"type": "string", "description": "image/jpeg 或 image/png"},
        },
        "required": ["image_base64"],
    },
    "output": {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "lines": {"type": "array", "items": {"type": "string"}},
            "provider": {"type": "string"},
            "ms": {"type": "integer"},
            "chars": {"type": "integer"},
            "error": {"type": ["string", "null"]},
        },
    },
    "limits": {"max_bytes": MAX_BYTES, "timeout_ms": 20000},
    "privacy": "原图仅在内存处理，不落盘、不入库；返回前对卡号/身份证/手机号/验证码打码。",
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        # 只记路径和状态，不记请求体
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
            st = ocr.status()
            return self._json(200, {"ok": True, **st})
        return self._json(200, SCHEMA)

    def do_POST(self):
        if not self.path.startswith("/ocr_extract"):
            return self._json(404, {"error": "not found"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_BYTES * 2:
                return self._json(413, {"error": "too large"})
            payload = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        except Exception:
            return self._json(400, {"error": "bad json"})

        b64 = (payload.get("image_base64") or "").strip()
        if b64.startswith("data:"):
            b64 = b64.split(",", 1)[-1]
        if not b64:
            return self._json(400, {"error": "empty image"})

        import base64

        try:
            raw = base64.b64decode(b64, validate=False)
        except Exception:
            return self._json(400, {"error": "bad base64"})
        if len(raw) > MAX_BYTES:
            return self._json(413, {"error": "image too large, please compress"})
        if not raw:
            return self._json(400, {"error": "empty image"})

        return self._json(200, ocr.extract(raw))


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8790
    st = ocr.status()
    print("=" * 56)
    print("  ocr_extract Skill")
    print("  provider: %s" % st["provider_label"])
    print("  地址: http://127.0.0.1:%d/ocr_extract" % port)
    print("=" * 56)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
