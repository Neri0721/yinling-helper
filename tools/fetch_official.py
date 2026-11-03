# -*- coding: utf-8 -*-
"""
补数据：从中国互联网联合辟谣平台抓官方条目，追加进 kb.json

为什么需要：现有 19,377 条里只有 122 条是 official，占 0.6%。
而方案里最硬的卖点是「可追溯到官方原文」——数据不补，这个卖点就是空的。

做法：
  1. 抓列表页（含分页），收集文章链接
  2. 逐篇抓正文，提取标题与段落
  3. 打上 tier=official、日期、来源
  4. 按 URL 去重后追加进 kb.json（先备份）

用法：
    python tools/fetch_official.py --max 80          # 先试列表页（能抓到多少算多少）
    python tools/fetch_official.py --urls urls.txt   # 推荐：自己复制链接，批量抓正文
    python tools/fetch_official.py --domain 政策      # 只留某个领域

关于 urls.txt：官方站的列表页是 JS 渲染的，脚本翻不到分页，
所以最靠谱的补数据方式是人工翻几页、把文章链接复制进一个文本文件（一行一个），
再由脚本批量抓正文、清洗、入库。

注意：只抓正文，不抓图片；每篇间隔 0.4 秒，别把人家站点打穿。
"""

import argparse
import json
import os
import re
import shutil
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
KB_PATH = os.path.join(PROJ, "kb.json")

BASE = "https://www.piyao.org.cn"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

LIST_PAGES = ["/jj.htm", "/ld.htm", "/gz.htm", "/rm.htm", "/ft.htm"]
MAX_PAGE = 12          # 每个栏目最多翻几页
MAX_BODY = 1500        # 单篇正文上限，超出的交给切分脚本处理

ART_RE = re.compile(r"/(\d{8})/([0-9a-f]{32})/c\.html")

DOMAINS = {
    "健康": ["保健品", "偏方", "秘方", "治好", "根治", "降血糖", "降血压", "抗癌", "排毒",
             "停药", "药到病除", "祖传", "神药", "包治", "癌", "血糖", "血压", "养生"],
    "钱财": ["转账", "汇款", "验证码", "银行卡", "公检法", "安全账户", "洗钱", "刷单", "返利",
             "中奖", "免费领", "投资", "理财", "基金", "养老金", "补贴", "退税", "征信", "诈骗"],
    "政策": ["政策", "新规", "社保", "医保", "退休", "公积金", "个税", "发放", "缴费",
             "退休金", "补贴标准", "调整", "假期", "年假"],
    "儿童": ["儿童", "孩子", "学生", "校园", "未成年", "幼儿园", "小学", "家长", "小朋友"],
}


def http_text(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    for enc in ("utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def strip_tags(html):
    h = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", html)
    h = re.sub(r"(?s)<[^>]+>", "\n", h)
    h = (h.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"')
         .replace("&lt;", "<").replace("&gt;", ">").replace("&#39;", "'"))
    return h


def domain_of(text):
    best, hit = "其他", 0
    for name, words in DOMAINS.items():
        n = sum(1 for w in words if w in text)
        if n > hit:
            best, hit = name, n
    return best


def collect_links():
    """遍历栏目页与分页，收集文章链接"""
    links = []
    for path in LIST_PAGES:
        for page in range(1, MAX_PAGE + 1):
            url = BASE + path if page == 1 else "%s%s_%d.htm" % (BASE, path[:-4], page)
            try:
                html = http_text(url)
            except Exception:
                break
            found = ART_RE.findall(html)
            if not found:
                break
            before = len(links)
            for date_str, aid in found:
                links.append("%s/%s/%s/c.html" % (BASE, date_str, aid))
            links = list(dict.fromkeys(links))
            print("  %s 第 %d 页 +%d" % (path, page, len(links) - before))
            time.sleep(0.3)
    return links


def parse_article(url, html):
    m = ART_RE.search(url)
    date_str = m.group(1) if m else ""
    date = "%s-%s" % (date_str[:4], date_str[4:6]) if date_str else ""

    title = ""
    tm = re.search(r"(?is)<title>(.*?)</title>", html)
    if tm:
        title = re.sub(r"\s*[-—_|]\s*中国互联网联合辟谣平台\s*$", "", tm.group(1).strip())
    if not title:
        h1 = re.search(r"(?is)<h1[^>]*>(.*?)</h1>", html)
        if h1:
            title = re.sub(r"<[^>]+>", "", h1.group(1)).strip()

    text = strip_tags(html)
    lines = []
    for ln in text.split("\n"):
        ln = ln.strip()
        if len(ln) < 15:
            continue
        if not re.search(r"[\u4e00-\u9fa5]", ln):
            continue
        if ln in ("打印本页", "关闭窗口", "分享到"):
            continue
        if ln == title:
            continue
        lines.append(ln)
    body = "".join(lines)
    return title, body[:MAX_BODY], date


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=80, help="本次最多抓多少篇")
    ap.add_argument("--domain", default="", help="只要某个领域：健康/钱财/政策/儿童")
    ap.add_argument("--urls", default="", help="链接清单文本文件，一行一个；给了就不走列表页")
    ap.add_argument("--dry-run", action="store_true", help="只统计不写回")
    args = ap.parse_args()

    with open(KB_PATH, encoding="utf-8") as f:
        kb = json.load(f)
    items = kb.get("items", [])
    have = {it.get("url") for it in items}
    print("现有条目 %d（其中官方 %d）" % (
        len(items), sum(1 for i in items if i.get("tier") == "official")))

    if args.urls:
        with open(args.urls, encoding="utf-8") as f:
            links = [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
        print("从 %s 读到 %d 个链接" % (args.urls, len(links)))
    else:
        print("收集链接…")
        links = collect_links()
    todo = [u for u in links if u not in have]
    print("共 %d 条，未入库 %d 条" % (len(links), len(todo)))

    added, skipped, by_dom = [], 0, {}
    for i, url in enumerate(todo[: args.max], 1):
        try:
            html = http_text(url)
            title, body, date = parse_article(url, html)
        except Exception as e:
            skipped += 1
            print("  [%d] 失败 %s %s" % (i, url[-40:], str(e)[:40]))
            continue
        if not title or len(body) < 30:
            skipped += 1
            continue
        dom = domain_of(title + body)
        if args.domain and dom != args.domain:
            skipped += 1
            continue
        by_dom[dom] = by_dom.get(dom, 0) + 1
        added.append({
            "title": title,
            "url": url,
            "snippet": body,
            "date": date,
            "chars": len(body),
            "tier": "official",
            "source": "中国互联网联合辟谣平台",
        })
        print("  [%d] %s（%s，%d 字）" % (i, title[:26], dom, len(body)))
        time.sleep(0.4)

    print("\n新增 %d 条，跳过 %d 条" % (len(added), skipped))
    print("按领域:", by_dom)

    if args.dry_run:
        print("dry-run，未写回")
        return
    if not added:
        print("没有新增，未写回")
        return

    shutil.copyfile(KB_PATH, KB_PATH + ".bak")
    items.extend(added)
    kb["items"] = items
    kb["built"] = time.strftime("%Y-%m-%d %H:%M")
    with open(KB_PATH, "w", encoding="utf-8") as f:
        json.dump(kb, f, ensure_ascii=False, indent=1)

    total = len(items)
    off = sum(1 for i in items if i.get("tier") == "official")
    print("写回完成：总 %d 条，官方 %d 条（%.1f%%），备份 kb.json.bak" % (
        total, off, off * 100.0 / total))
    print("下一步：python tools/prep_kb.py 重新生成导入包")


if __name__ == "__main__":
    main()
