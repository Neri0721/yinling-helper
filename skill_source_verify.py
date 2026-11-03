# -*- coding: utf-8 -*-
"""
银龄核查助手 · Skill 服务：source_verify

用途：给定一个 URL，判断是否属于权威来源白名单，并在可抓取时摘出正文片段。
      只描述"这个来源是什么等级、原文大概说了什么"，不判断 URL 内容的真假。

启动：
    python skill_source_verify.py       # 默认 8792
    python skill_source_verify.py 9001

接口契约：
    POST /source_verify
      {"url": "https://www.piyao.org.cn/..."}
    → {"official": true, "tier": "official", "source_name": "中国互联网联合辟谣平台",
       "excerpt": "...", "source_type": "official", "error": null}

    GET  /health → {"ok": true, "whitelist": 10, "media": 6}
    GET  /       → schema

复用：server.py 的 whitelisted() / source_tier() / page_text() / _source_name() /
      _media_name()，不复制判级逻辑。

tier 解释（与知识库三值保持一致）：
    official  政府/官方白名单来源
    media     央媒/官方科普
    dataset   其他网络来源（含无法识别），只能作线索，不能当官方依据

安全：只接受 http/https；抓取前解析域名并拒绝内网/回环/链路本地地址（防 SSRF）。
"""

import ipaddress
import json
import os
import socket
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import server as core  # noqa: E402  复用白名单与抓正文实现

MAX_URL = 2048
FETCH_TIMEOUT_MS = 20000

SCHEMA = {
    "skill": "source_verify",
    "version": "1.0",
    "description": "判断 URL 是否为权威来源，并在允许时摘录正文。只标来源等级，不判内容真假。",
    "input": {
        "type": "object",
        "properties": {"url": {"type": "string", "description": "http/https 网址"}},
        "required": ["url"],
    },
    "output": {
        "type": "object",
        "properties": {
            "official": {"type": "boolean"},
            "tier": {"type": "string", "enum": ["official", "dataset", "media"]},
            "source_name": {"type": "string"},
            "excerpt": {"type": "string"},
            "source_type": {"type": "string",
                            "enum": ["official", "media", "web", "unknown"]},
            "error": {"type": ["string", "null"]},
        },
    },
    "limits": {"max_url_chars": MAX_URL, "timeout_ms": FETCH_TIMEOUT_MS},
    "notes": "official 只由白名单域名决定；excerpt 抓不到时为空并置 error，不影响 official。",
}


def clip(text, n):
    text = text or ""
    return text if len(text) <= n else text[:n - 1] + "…"


def _host_of(url):
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def _safe_to_fetch(url):
    """只允许公网 http/https，拒绝内网/回环/链路本地地址。"""
    try:
        p = urlparse(url)
    except Exception:
        return False, "invalid_url"
    if p.scheme not in ("http", "https"):
        return False, "invalid_scheme"
    host = (p.hostname or "").lower()
    if not host or host in ("localhost",) or host.endswith(".local"):
        return False, "invalid_url"
    try:
        infos = socket.getaddrinfo(host, p.port or (443 if p.scheme == "https" else 80),
                                   proto=socket.IPPROTO_TCP)
    except Exception:
        return False, "dns_failed"
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False, "invalid_url"
        if not ip.is_global:
            return False, "private_address"
    return True, None


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
                "whitelist": len(core.WHITELIST),
                "media": len(core.MEDIA_WHITELIST),
                "timeout_ms": FETCH_TIMEOUT_MS,
            })
        return self._json(200, SCHEMA)

    def do_POST(self):
        if not self.path.startswith("/source_verify"):
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

        url = (payload.get("url") or "").strip()
        if not url:
            return self._json(400, {"error": "empty url"})
        if len(url) > MAX_URL:
            return self._json(400, {"error": "url too long"})
        if urlparse(url).scheme not in ("http", "https"):
            return self._json(400, {"error": "invalid url scheme"})

        official = core.whitelisted(url)
        raw_tier = core.source_tier(url)
        host = _host_of(url)
        if official:
            tier, source_type, name = "official", "official", core._source_name(url)
        elif raw_tier == "media":
            tier, source_type, name = "media", "media", core._media_name(url)
        else:
            tier, source_type, name = "dataset", (raw_tier or "unknown"), host

        excerpt, error = "", None
        if official or raw_tier == "media":
            safe, reason = _safe_to_fetch(url)
            if not safe:
                error = reason
            else:
                try:
                    lines = core.page_text(url)
                except Exception as e:
                    lines = []
                    error = "fetch_failed: %s" % str(e)[:60]
                if lines:
                    excerpt = clip(" ".join(lines[:3]), 300)
                elif error is None:
                    error = "fetch_failed"
        else:
            error = "not_authoritative"

        return self._json(200, {
            "official": official,
            "tier": tier,
            "source_name": name,
            "excerpt": excerpt,
            "source_type": source_type,
            "error": error,
        })


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8792
    print("=" * 56)
    print("  source_verify Skill")
    print("  白名单: %d  央媒: %d" % (len(core.WHITELIST), len(core.MEDIA_WHITELIST)))
    print("  地址: http://127.0.0.1:%d/source_verify" % port)
    print("=" * 56)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()