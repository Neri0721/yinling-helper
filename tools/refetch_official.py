# -*- coding: utf-8 -*-
"""
回抓官方原文正文

问题：kb.json 里 tier=official 的 122 条，正文中位数只有 91 字——那是搜索摘要，
      不是文章正文。拿它当"权威依据"给老人看，等于给了一句话的残片。

做法：逐条打开原文，抽取正文段落（每段≥15 字且含中文），
      正文比原来长就替换，并补上 source_name（机构名）与 retrieved_at（抓取时间）。

用法：
    python tools/refetch_official.py            # 全量回抓
    python tools/refetch_official.py --limit 10 # 先试 10 条
"""

import argparse
import json
import os
import re
import shutil
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
KB_PATH = os.path.join(PROJ, "kb.json")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
MAX_BODY = 1500

SOURCE_NAMES = [
    ("piyao.org.cn", "中国互联网联合辟谣平台"),
    ("12377.cn", "中央网信办举报中心"),
    ("gov.cn", "中国政府网"),
    ("nhc.gov.cn", "国家卫生健康委员会"),
    ("chinacdc.cn", "中国疾病预防控制中心"),
    ("samr.gov.cn", "国家市场监督管理总局"),
    ("12315.cn", "全国 12315 平台"),
    ("mps.gov.cn", "公安部"),
    ("nmpa.gov.cn", "国家药品监督管理局"),
    ("cac.gov.cn", "国家互联网信息办公室"),
]


def http_text(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        enc = (r.headers.get("Content-Encoding") or "").lower()
    import gzip
    if enc == "gzip" or raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    for e in ("utf-8", "gb18030"):
        try:
            return raw.decode(e)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def body_of(html):
    h = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", html)
    h = re.sub(r"(?s)<[^>]+>", "\n", h)
    h = (h.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"')
         .replace("&lt;", "<").replace("&gt;", ">").replace("&#39;", "'"))
    keep = []
    for ln in h.split("\n"):
        ln = ln.strip()
        if len(ln) < 15 or not re.search(r"[\u4e00-\u9fa5]", ln):
            continue
        if ln.startswith(("打印", "关闭窗口", "分享", "扫一扫", "责任编辑")):
            continue
        keep.append(ln)
    return "".join(keep)[:MAX_BODY]


def source_name(url):
    host = re.sub(r"^https?://", "", url).split("/")[0].lower()
    for d, n in SOURCE_NAMES:
        if host == d or host.endswith("." + d):
            return n
    return host


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    with open(KB_PATH, encoding="utf-8") as f:
        kb = json.load(f)
    items = kb.get("items", [])
    off = [(i, it) for i, it in enumerate(items) if it.get("tier") == "official"]
    if args.limit:
        off = off[: args.limit]
    print("待回抓 %d 条" % len(off))

    before = sum(len(it.get("snippet", "")) for _i, it in off)
    ok = fail = 0
    for n, (idx, it) in enumerate(off, 1):
        url = it.get("url", "")
        if not url.startswith("http"):
            fail += 1
            continue
        try:
            html = http_text(url)
            body = body_of(html)
        except Exception as e:
            fail += 1
            print("  [%d] 失败 %s %s" % (n, url[-36:], str(e)[:40]))
            time.sleep(0.3)
            continue
        if len(body) > len(it.get("snippet", "")) + 20:
            items[idx]["snippet"] = body
            items[idx]["chars"] = len(body)
            ok += 1
        items[idx]["source_name"] = source_name(url)
        items[idx]["retrieved_at"] = time.strftime("%Y-%m-%d")
        print("  [%d] %s  %d → %d 字" % (
            n, it["title"][:22], len(it.get("snippet", "")), len(items[idx]["snippet"])))
        time.sleep(0.4)

    after = sum(len(it.get("snippet", "")) for _i, it in off)
    print("\n成功 %d，失败 %d" % (ok, fail))
    print("正文总长 %d → %d 字（%.1f 倍）" % (
        before, after, after / max(before, 1)))

    if ok == 0:
        print("没有改进，未写回")
        return
    shutil.copyfile(KB_PATH, KB_PATH + ".bak")
    kb["items"] = items
    kb["built"] = time.strftime("%Y-%m-%d %H:%M")
    with open(KB_PATH, "w", encoding="utf-8") as f:
        json.dump(kb, f, ensure_ascii=False, indent=1)
    print("已写回，备份 kb.json.bak")
    print("下一步：python tools/filter_elderly.py 然后 python tools/prep_kb.py")


if __name__ == "__main__":
    main()
