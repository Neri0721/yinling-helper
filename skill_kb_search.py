# -*- coding: utf-8 -*-
"""
银龄核查助手 · Skill 服务：kb_search

用途：把"在银龄子集里找证据"单独暴露成 HTTP 能力，供 AgentArts 包装成插件。
      只做检索，不做真假判断；没检索到就返回空列表，不许编造。

启动：
    python skill_kb_search.py           # 默认 8791
    python skill_kb_search.py 9001

接口契约：
    POST /kb_search
      {"query": "喝骨头汤能补钙吗", "domain": "健康", "top_k": 5}
    → {"hits": [{"id", "title", "snippet", "tier", "url", "date", "score"}],
       "query": "...", "domain": "...", "top_k": 5, "total": 3, "ms": 12}

    GET  /health → {"ok": true, "docs": 3188, "terms": 53517, "source": "..."}
    GET  /       → 本文件开头的 schema

数据源：tools/out/kb_import_elderly.jsonl（子集口径，3,188 块）。
文件缺失时服务仍可启动，但 /health 返回 ok=false，POST 返回 503，不静默返回空结果。
"""

import json
import math
import os
import re
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "tools", "out", "kb_import_elderly.jsonl")

MAX_QUERY = 200
DEFAULT_TOP_K = 5
MAX_TOP_K = 20

CLEAN = re.compile(r"[^\u4e00-\u9fa5A-Za-z0-9]")

SCHEMA = {
    "skill": "kb_search",
    "version": "1.0",
    "description": "在银龄子集知识库里做字符二元组检索，返回可追溯的证据条目。只检索，不判真假。",
    "input": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "待核查的说法或关键词，最长 200 字"},
            "domain": {"type": "string",
                       "description": "可选：健康 / 钱财 / 政策 / 儿童 / 其他"},
            "top_k": {"type": "integer", "description": "返回条数，默认 5，最大 20"},
        },
        "required": ["query"],
    },
    "output": {
        "type": "object",
        "properties": {
            "hits": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "title": {"type": "string"},
                        "snippet": {"type": "string"},
                        "tier": {"type": "string", "enum": ["official", "dataset", "media"]},
                        "url": {"type": "string"},
                        "date": {"type": "string"},
                        "score": {"type": "number"},
                    },
                },
            },
            "query": {"type": "string"},
            "domain": {"type": ["string", "null"]},
            "top_k": {"type": "integer"},
            "total": {"type": "integer"},
            "ms": {"type": "integer"},
        },
    },
    "limits": {"max_query_chars": MAX_QUERY, "max_top_k": MAX_TOP_K, "timeout_ms": 3000},
    "notes": "score 是字符二元组 IDF 加权和，只用于排序，不是概率；tier 严格三值。",
}


def grams(text):
    s = CLEAN.sub("", (text or "").lower())
    return {s[i:i + 2] for i in range(len(s) - 1)}


def clip(text, n):
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if len(text) <= n else text[:n - 1] + "…"


class Index:
    def __init__(self, path):
        self.path = path
        self.docs = []
        self.ids = []
        self.grams_of = []
        self.index = {}
        self.idf = {}
        self.ok = False
        self.error = None
        self.index_ms = 0
        self.load()

    def load(self):
        if not os.path.exists(self.path):
            self.error = "数据文件不存在：%s" % os.path.relpath(self.path, HERE)
            return
        t0 = time.time()
        try:
            with open(self.path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self.docs.append(json.loads(line))
        except Exception as e:
            self.error = "数据读取失败：%s" % str(e)[:120]
            return
        n = len(self.docs)
        if not n:
            self.error = "数据文件为空"
            return
        df = {}
        for i, it in enumerate(self.docs):
            self.ids.append(it.get("id", ""))
            g = grams(it.get("content", "") + " " + it.get("title", ""))
            self.grams_of.append(g)
            for gram in g:
                df[gram] = df.get(gram, 0) + 1
                self.index.setdefault(gram, []).append(i)
        self.idf = {g: math.log((n + 1.0) / (c + 1.0)) + 1.0 for g, c in df.items()}
        self.ok = True
        self.index_ms = int((time.time() - t0) * 1000)

    def search(self, query, domain=None, top_k=DEFAULT_TOP_K):
        qg = grams(query)
        scores = {}
        for gram in qg:
            for d in self.index.get(gram, ()):
                if domain and self.docs[d].get("metadata", {}).get("domain") != domain:
                    continue
                scores[d] = scores.get(d, 0.0) + self.idf.get(gram, 1.0)
        ranked = sorted(scores.items(), key=lambda x: -x[1])[:top_k]
        hits = []
        for d, s in ranked:
            it = self.docs[d]
            meta = it.get("metadata", {}) or {}
            body = (it.get("content") or "").split("\n", 1)[-1]
            hits.append({
                "id": it.get("id", ""),
                "title": it.get("title", ""),
                "snippet": clip(body, 80),
                "tier": meta.get("tier", ""),
                "url": meta.get("url", ""),
                "date": meta.get("date", ""),
                "score": round(float(s), 3),
            })
        return hits


IDX = Index(DATA)


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
                "ok": IDX.ok,
                "docs": len(IDX.docs),
                "terms": len(IDX.index),
                "source": os.path.basename(DATA),
                "index_ms": IDX.index_ms,
                "error": IDX.error,
            })
        return self._json(200, SCHEMA)

    def do_POST(self):
        if not self.path.startswith("/kb_search"):
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

        query = (payload.get("query") or "").strip()
        if not query:
            return self._json(400, {"error": "empty query"})
        if len(query) > MAX_QUERY:
            return self._json(400, {"error": "query too long, max %d chars" % MAX_QUERY})

        domain = (payload.get("domain") or "").strip() or None
        try:
            top_k = int(payload.get("top_k") or DEFAULT_TOP_K)
        except (TypeError, ValueError):
            return self._json(400, {"error": "bad top_k"})
        if top_k < 1 or top_k > MAX_TOP_K:
            return self._json(400, {"error": "top_k must be 1-%d" % MAX_TOP_K})

        if not IDX.ok:
            return self._json(503, {"error": "index unavailable", "detail": IDX.error})

        t0 = time.time()
        hits = IDX.search(query, domain=domain, top_k=top_k)
        return self._json(200, {
            "hits": hits,
            "query": query,
            "domain": domain,
            "top_k": top_k,
            "total": len(hits),
            "ms": int((time.time() - t0) * 1000),
        })


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8791
    print("=" * 56)
    print("  kb_search Skill")
    print("  文档数: %d  词表: %d" % (len(IDX.docs), len(IDX.index)))
    print("  数据源: %s" % os.path.basename(DATA))
    if not IDX.ok:
        print("  [WARN] %s" % IDX.error)
    print("  地址: http://127.0.0.1:%d/kb_search" % port)
    print("=" * 56)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()