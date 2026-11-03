"""
银龄核查助手 · 本地服务
- 静态页面：本目录下的 index.html / style.css / app.js
- 核查接口：POST /api/check {"text": "..."} → 返回卡片 JSON（严格按提示词 v2 的字段）
- 设计原则：无据不判。知识库未命中且无实时检索结果时，一律返回"暂无权威结论"。
"""

import json
import os
import re
import socket
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
KB_PATH = os.path.join(HERE, "kb.json")
KB_FALLBACK_PATH = os.path.join(HERE, "kb_elderly.json")
KB_SOURCE = None
OFFLINE = os.environ.get("OFFLINE") == "1"

# 本地大模型（Ollama）——可选依赖，连不上就退回纯规则模式
try:
    sys.path.insert(0, HERE)
    import llm  # noqa: E402
except Exception as _e:  # pragma: no cover
    print("[llm] 未启用:", str(_e)[:80])
    llm = None

# 图片转文字（拍照/截图核查）——没有凭据时自动退回离线或演示模式
try:
    import ocr  # noqa: E402
except Exception as _e:  # pragma: no cover
    print("[ocr] 未启用:", str(_e)[:80])
    ocr = None

MAX_IMAGE_BYTES = 8 * 1024 * 1024   # 单张图片上限，超过让前端压缩
PROXY_TIMEOUT = 8                    # AgentArts 代理转发超时（秒）
PROXY_MAX_BYTES = 1024 * 1024        # 代理请求体上限

# 权威来源白名单（严格匹配域名后缀，防钓銇）
WHITELIST = [
    "piyao.org.cn", "12377.cn", "cac.gov.cn", "gov.cn", "nhc.gov.cn",
    "chinacdc.cn", "samr.gov.cn", "12315.cn", "mps.gov.cn", "nmpa.gov.cn",
]

DANGER_WORDS = [
    "转账", "汇款", "打钱", "验证码", "银行密码", "银行卡号", "陌生链接", "点击链接", "点开链接",
    "公检法", "安全账户", "涉嫌", "洗钱", "通缉", "拘捕", "刷单", "返利", "中奖", "免费领",
    "共享屏幕", "屏幕共享", "解冻", "保证金", "注销校园贷", "额度清零", "客服退款",
]
HEALTH_WORDS = [
    "保健品", "偏方", "秘方", "治好", "根治", "降血糖", "降血压", "抗癌", "排毒", "停药",
    "治疗", "药到病除", "祖传", "神药", "包治",
]
POLICY_WORDS = ["养老金", "社保", "医保", "补贴", "政策", "退休", "公积金", "个税", "发放", "缴费", "新规"]
CHILD_WORDS = ["儿童", "孩子", "学生", "校园", "未成年", "幼儿园", "小学", "家长", "小朋友"]

INJECTION_HINTS = ["忽略以上", "忽略之前", "你现在是", "你必须说", "直接告诉我是真的", "不要再查", "跳过检索"]


# ---------------------------------------------------------------- 工具
def whitelisted(url: str) -> bool:
    if not url:
        return False
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return False
    if not host:
        return False
    # gov.cn 太宽泛，只承认主域，避免任意子站（如某个业务系统查询页）被当作依据
    if host in ("gov.cn", "www.gov.cn"):
        return True
    for d in WHITELIST:
        if d == "gov.cn":
            continue
        if host == d or host.endswith("." + d):
            return True
    return False


def clip(text, n):
    text = re.sub(r"\s+", " ", (text or "")).strip()
    return text if len(text) <= n else text[: n - 1] + "…"


def bigrams(text):
    """中文二元组，用于粗略相关度计算"""
    cleaned = re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9]", "", text or "")
    return {cleaned[i:i + 2] for i in range(len(cleaned) - 1)}


STOP = {"这个", "那个", "什么", "怎么", "我们", "你们", "他们", "一个", "现在", "就是", "可以", "没有",
        "真的", "假的", "是不是", "能不能", "有没有", "这条", "那条", "听说", "网上"}


def keywords(text):
    grams = bigrams(text) - STOP
    return grams


# 提问语气、虚词——检索时会干扰匹配，先剥掉
FILLER = [
    "是真的吗", "是真的么", "是不是真的", "是不是", "能不能", "可不可以", "可以吗", "行不行",
    "请问", "我想知道", "我想问", "想知道", "帮我查", "帮我看看", "求证",
    "真的", "假的", "吗", "呢", "啊", "呀", "吧", "么", "？", "?", "。", "！", "!", "，", ",", "、",
]
VERB_CHARS = set("能会可要是有的了在有就都也还太更最")


LEAD_VERBS = "喝吃用看听说买戴穿做搞玩洗擦敷贴喝吃"


def clean_query(text):
    """把一句口语提问压成检索用的关键词串"""
    t = re.sub(r"\s+", "", text or "")
    for f in FILLER:
        t = t.replace(f, "")
    # 去掉连续的虚词，但保留原有实词顺序
    t = "".join(ch for ch in t if ch not in VERB_CHARS)
    # 开头的单字动词会误导搜索引擎（“喝骨头汤”被当成查“喝”），剥掉
    while len(t) > 3 and t[0] in LEAD_VERBS:
        t = t[1:]
    return t[:24]


def classify(text):
    cats = []
    if any(w in text for w in HEALTH_WORDS):
        cats.append("健康")
    if any(w in text for w in DANGER_WORDS):
        cats.append("钱财")
    if any(w in text for w in POLICY_WORDS):
        cats.append("政策")
    if any(w in text for w in CHILD_WORDS):
        cats.append("儿童")
    return cats or ["其他"]


def extract_claim(text):
    t = re.sub(r"\s+", " ", text or "").strip()
    for p in ["我听说", "听说", "有人说", "网上说", "群里说", "朋友圈说", "朋友说", "我妈说", "我爸说",
              "我收到", "收到一条", "看到一条", "帮我看看", "帮我查查", "这个是不是真的", "是真的吗"]:
        if t.startswith(p):
            t = t[len(p):].lstrip("，,：: ")
    t = re.split(r"[。！？!?\n]", t)[0]
    return clip(t, 30)


def load_kb():
    """按 kb.json → kb_elderly.json 顺序加载；都没有则返回 []，由启动处告警。

    严禁静默变成 0 条：读到空文件也要打印来源，避免自测假绿。
    """
    global KB_SOURCE
    for path in (KB_PATH, KB_FALLBACK_PATH):
        if not os.path.exists(path):
            continue
        name = os.path.basename(path)
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            items = data.get("items", []) if isinstance(data, dict) else []
        except Exception as e:
            print("[WARN] 知识库读取失败 %s: %s" % (name, str(e)[:60]))
            continue
        if items:
            KB_SOURCE = name
            return items
        print("[WARN] 知识库为空: %s" % name)
    return []


def kb_match(text, kb, limit=1):
    """在知识库里找最相关条目，返回 [(score, item)]，原句与清洗词各试一次取高分"""
    queries = [keywords(text), keywords(clean_query(text))]
    queries = [q for q in queries if len(q) >= 2]
    if not queries:
        return []
    best = {}
    for q in queries:
        min_common = 2 if len(q) > 4 else 1
        for it in kb:
            hay = (it.get("title", "") * 2) + " " + it.get("snippet", "")
            h = keywords(hay)
            common = q & h
            if len(common) < min_common:
                continue
            score = len(common) / max(min(len(q), 8), 1)
            key = it.get("url") or it.get("title")
            if key not in best or score > best[key][0]:
                best[key] = (score, it)
    scored = sorted(best.values(), key=lambda x: -x[0])
    return scored[:limit]


# ---------------------------------------------------------------- 实时检索（白名单限定）
import base64
import gzip
import html as _htmllib
import urllib.error
import urllib.parse
import urllib.request
import zlib

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

_cache = {}


def _http(url, referer=None, timeout=12):
    headers = {"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        enc = (r.headers.get("Content-Encoding") or "").lower()
    # 有些政务站会 gzip/deflate 压缩，直接当文本解码就会变乱码
    try:
        if enc == "gzip" or raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        elif enc == "deflate":
            try:
                raw = zlib.decompress(raw)
            except Exception:
                raw = zlib.decompress(raw, -zlib.MAX_WBITS)
        elif enc == "br":
            print("[http] brotli 压缩不支持，跳过:", url[:60])
            return b""
    except Exception as e:
        print("[http] 解压失败:", str(e)[:50], url[:50])
        return b""
    return raw


def _looks_garbage(s):
    """判断文本是否像乱码：中文太少、或不可打印字符占比过高"""
    if not s or len(s) < 8:
        return True
    cjk = len(re.findall(r"[\u4e00-\u9fa5]", s))
    if cjk < 4:
        return True
    good = len(re.findall(r"[\u4e00-\u9fa5A-Za-z0-9，。、；：！？（）《》“”‘’—…·%+\-/\s]", s))
    return good / max(len(s), 1) < 0.75


def _decode_bing(u):
    if not u or not u.startswith("a1"):
        return None
    s = u[2:] + "=" * (-len(u[2:]) % 4)
    try:
        return base64.urlsafe_b64decode(s).decode("utf-8", "replace")
    except Exception:
        return None


def bing_search(query, count=20):
    """免密钥检索：解析 Bing RSS，返回 [{title, url, desc}]"""
    url = "https://www.bing.com/search?" + urllib.parse.urlencode(
        {"q": query, "format": "rss", "count": count, "setlang": "zh-CN"})
    try:
        body = _http(url).decode("utf-8", "replace")
    except Exception as e:
        print("[live] 搜索失败:", str(e)[:60])
        return []
    out, seen = [], set()
    for item in re.findall(r"(?is)<item>(.*?)</item>", body):
        def pick(tag):
            m = re.search(r"(?is)<%s>(.*?)</%s>" % (tag, tag), item)
            if not m:
                return ""
            v = m.group(1)
            v = re.sub(r"(?is)<!\[CDATA\[(.*?)\]\]>", r"\1", v)
            v = re.sub(r"(?s)<[^>]+>", " ", v)
            return _htmllib.unescape(v).strip()

        link = pick("link")
        if not link or "bing.com" in link or link in seen:
            continue
        seen.add(link)
        out.append({"title": pick("title"), "url": link, "desc": pick("description")})
    return out


# 权威媒体/官方科普（非政府站，但属央媒或官方科普）——命中时按“媒体来源”标注
MEDIA_WHITELIST = [
    "news.cn", "xinhuanet.com", "people.com.cn", "cctv.com",
    "chinanews.com.cn", "kepuchina.cn",
]


# 网络参考（网友讨论/百科）—— 只作线索，不能当权威依据
WEB_SOURCES = [
    "zhidao.baidu.com", "tieba.baidu.com", "baike.baidu.com", "baidu.com",
    "zhihu.com", "douban.com", "weibo.com", "sina.com.cn", "sohu.com", "163.com",
]

WEB_NAMES = {
    "zhidao.baidu.com": "百度知道", "tieba.baidu.com": "百度贴吧",
    "baike.baidu.com": "百度百科", "baidu.com": "百度",
    "zhihu.com": "知乎", "douban.com": "豆瓣", "weibo.com": "微博",
    "sina.com.cn": "新浪", "sohu.com": "搜狐", "163.com": "网易",
}

# 问答类（有观点/结论）优先于百科定义类，后者往往答非所问
WEB_PRIO = {
    "zhidao.baidu.com": 0, "tieba.baidu.com": 1, "zhihu.com": 2,
    "baike.baidu.com": 5, "baidu.com": 6,
}


def _web_prio(url):
    host = (urlparse(url).hostname or "").lower()
    for d, p in WEB_PRIO.items():
        if host == d or host.endswith("." + d):
            return p
    return 4


def source_tier(url):
    """返回 'official' / 'media' / 'web' / None"""
    if not url:
        return None
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return None
    if whitelisted(url):
        return "official"
    for d in MEDIA_WHITELIST:
        if host == d or host.endswith("." + d):
            return "media"
    for d in WEB_SOURCES:
        if host == d or host.endswith("." + d):
            return "web"
    return None


def _web_name(url):
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return "网络来源"
    for d, n in WEB_NAMES.items():
        if host == d or host.endswith("." + d):
            return n
    return host


MEDIA_NAMES = {
    "news.cn": "新华网", "xinhuanet.com": "新华网", "people.com.cn": "人民网",
    "cctv.com": "央视网", "kepuchina.cn": "科普中国",
    "chinanews.com.cn": "中国新闻网",
}


def _media_name(url):
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return "媒体"
    for d, n in MEDIA_NAMES.items():
        if host == d or host.endswith("." + d):
            return n
    return host


DEBUNK_MARKERS = ["谣言", "辟谣", "不实", "系谣传", "纯属虚构", "勿信", "假的", "不要相信", "不要轻信"]


def page_text(url):
    raw = _http(url, referer="https://www.piyao.org.cn/", timeout=15)
    if not raw:
        return []
    # 按声明编码优先解码，并逐一校验是否为乱码
    t = ""
    for enc in ("utf-8", "gb18030", "gbk", "big5"):
        try:
            cand = raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
        if cand.count("\ufffd") < 5 and not _looks_garbage(cand[:2000]):
            t = cand
            break
    if not t:
        print("[page] 解码失败或疑似乱码，跳过:", url[:70])
        return []
    t = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", t)
    t = re.sub(r"(?s)<[^>]+>", "\n", t)
    t = _htmllib.unescape(t).replace("\u3000", " ").replace("\xa0", " ")
    lines = [ln.strip() for ln in t.split("\n") if len(ln.strip()) >= 15]
    bad = ("Insert title here", "错误页", "页面不存在", "404", "JavaScript")
    out = []
    for ln in lines:
        if any(b in ln for b in bad):
            continue
        if not re.search(r"[\u4e00-\u9fa5]", ln):
            continue
        if _looks_garbage(ln):
            continue
        out.append(ln)
    return out


def zhidao_search(query, limit=6):
    """百度知道搜索（免密钥）：返回 [{title, url, desc}]"""
    url = "https://zhidao.baidu.com/search?word=" + urllib.parse.quote(query)
    try:
        html = _http(url, referer="https://zhidao.baidu.com/", timeout=15).decode("utf-8", "replace")
    except Exception as e:
        print("[zhidao] 搜索失败:", str(e)[:60])
        return []
    items = []
    for block in re.split(r'(?=<dt class="dt)', html)[1:]:
        m = re.search(r'href="(https?://zhidao\.baidu\.com/question/\d+\.html)[^"#]*"[^>]*>(.*?)</a>',
                      block, re.S)
        if not m:
            continue
        link = m.group(1)
        title = re.sub(r"<[^>]+>", "", m.group(2))
        title = _htmllib.unescape(re.sub(r"\s+", " ", title)).strip()
        if len(title) < 6:
            continue
        plain = _htmllib.unescape(re.sub(r"(?s)<[^>]+>", " ", block))
        plain = re.sub(r"\s+", " ", plain).strip()
        desc = plain.replace(title, " ", 1).strip()
        items.append({"title": title, "url": link, "desc": desc[:200]})
        if len(items) >= limit:
            break
    return items


def live_search(text):
    """知识库未命中时的联网检索：返回 {url, snippet, debunk, source_name, tier} 或 None"""
    key = "".join(sorted(keywords(text)))[:60]
    if key in _cache:
        return _cache[key]

    q_grams = keywords(text)
    core = clean_query(text) or text[:20]
    # 不加 site:（实测 Bing 忽略该语法），改为结果侧按来源分级过滤
    queries = [core, core + " 辟谣", core + " 谣言 真相"]

    for q in queries:
        try:
            links = bing_search(q)
        except Exception as e:
            print("[live] 搜索失败:", str(e)[:60])
            links = []
        # 首个查询额外拉一次百度知道（真正的“网友帖子”出处）
        if q == core:
            try:
                z = zhidao_search(core)
                if z:
                    links = z + links
            except Exception as e:
                print("[zhidao] 异常:", str(e)[:50])
        # 优先级：官方 > 央媒 > 网络参考（网络参考内部：问答类 > 百科）
        def _rank(it):
            t = source_tier(it["url"])
            base = {"official": 0, "media": 1, "web": 2}.get(t, 9)
            return (base, _web_prio(it["url"]) if t == "web" else 0)

        ranked = sorted([it for it in links if source_tier(it["url"])], key=_rank)
        for it in ranked[:5]:
            u = it["url"]
            tier = source_tier(u)
            # 权威来源要求 ≥2 个关键词重合；网络参考只要求 ≥1（它本就只是线索）
            need = 1 if tier == "web" else 2

            if tier == "web":
                # 百度百科/知乎普遍 403，直接用搜索摘要做证据，不去抓页面
                snippet = it.get("desc") or it.get("title") or ""
                body = snippet
                if len(set(keywords(snippet)) & q_grams) < need:
                    continue
                # 有出处但答非所问，等于没说；让本地模型判一下是否对题
                if llm and llm.available():
                    if llm.same_topic(text, snippet) is False:
                        print("[live] 网络参考答非所问，跳过:", u[:60])
                        continue
            else:
                try:
                    lines = page_text(u)
                except Exception:
                    lines = []
                if not lines:
                    # 抓不到正文（如 403）时退回搜索摘要，仍须满足重合度
                    snippet = it.get("desc") or ""
                    body = snippet
                    if len(set(keywords(snippet)) & q_grams) < need:
                        continue
                else:
                    body = " ".join(lines)
                    snippet = ""
                    for ln in lines:
                        if len(set(keywords(ln)) & q_grams) >= need and len(ln) >= 20:
                            snippet = ln
                            break
                    if not snippet:
                        if len(set(keywords(body)) & q_grams) < need:
                            continue
                        snippet = lines[0]
            if tier == "official":
                name = _source_name(u)
            elif tier == "media":
                name = _media_name(u)
            else:
                name = _web_name(u)
            res = {
                "url": u,
                "snippet": clip(snippet, 60),
                "full": clip(snippet, 400),
                "debunk": any(m in body for m in DEBUNK_MARKERS),
                "source_name": name,
                "tier": tier,
            }
            _cache[key] = res
            print("[live] 命中(%s) %s" % (tier, u[:70]))
            return res
    _cache[key] = None
    return None


def _source_name(url):
    host = (urlparse(url).hostname or "").lower()
    for d, n in [
        ("piyao.org.cn", "中国互联网联合辟谣平台"), ("12377.cn", "中央网信办举报中心"),
        ("gov.cn", "中国政府网"), ("nhc.gov.cn", "国家卫生健康委员会"),
        ("chinacdc.cn", "中国疾病预防控制中心"), ("samr.gov.cn", "国家市场监督管理总局"),
        ("12315.cn", "全国12315平台"), ("mps.gov.cn", "公安部"),
        ("nmpa.gov.cn", "国家药品监督管理局"), ("cac.gov.cn", "国家互联网信息办公室"),
    ]:
        if host == d or host.endswith("." + d):
            return n
    return host


# ---------------------------------------------------------------- 卡片生成
def build_card(text, kb):
    # 主张抽取：优先用本地模型（更懂口语），失败再退回规则
    claim = ""
    if llm and llm.available():
        claim = llm.extract_claim(text, fallback="")
    claim = claim or extract_claim(text) or clip(text, 30)

    cats = classify(text)
    danger = cats.count("钱财") > 0 or any(w in text for w in DANGER_WORDS)

    # 知识库匹配：用模型给的关键词再查一次，提高口语命中率
    extra_q = ""
    if llm and llm.available():
        extra_q = llm.search_keywords(claim, fallback="")

    hits = kb_match(text, kb, limit=8)
    if extra_q:
        hits2 = kb_match(extra_q, kb, limit=8)
        merged_hits = {}
        for s, it in (hits or []) + (hits2 or []):
            k = it.get("url") or it.get("title")
            if k not in merged_hits or s > merged_hits[k][0]:
                merged_hits[k] = (s, it)
        hits = sorted(merged_hits.values(), key=lambda x: -x[0])

    # 官方来源：0.45 + 模型复核；公开语料：0.45（阈值本身已较严）
    best = None
    ds_best = None
    for s, it in (hits or []):
        tier = it.get("tier", "official")
        if tier == "official" and best is None and s >= 0.45:
            best = (s, it)
        elif tier == "dataset" and ds_best is None and s >= 0.45:
            ds_best = (s, it)

    # 复核：知识库条目必须和用户问的是同一件事，否则宁可判“查不到”
    def _verify(cand):
        if not cand:
            return None
        if not (llm and llm.available()):
            return cand
        rec = (cand[1].get("title") or "") + "｜" + (cand[1].get("snippet") or "")
        verdict = llm.same_topic(claim, rec)
        if verdict is False:
            print("[verify] 丢弃不相关命中: %s" % (cand[1].get("title") or "")[:40])
            return None
        return cand

    best = _verify(best)
    # 公开语料只靠阈值把关（模型复核会把真阳性误杀），但命中后仍会标注来源等级

    live = None
    if not best and not ds_best and not OFFLINE:
        try:
            live = live_search(text)
        except Exception as e:
            print("[live] 异常:", str(e)[:80])

    if best:
        score, item = best
        url = item.get("url") if whitelisted(item.get("url", "")) else None
        evidence = clip(item.get("snippet", ""), 60)
        source_name = "中国互联网联合辟谣平台"
        if danger:
            risk = "高风险"
            conclusion = "这条多半是骗局，先别操作"
        elif "健康" in cats:
            risk = "高风险"
            conclusion = "这是谣言，别信也别用"
        else:
            risk = "高风险"
            conclusion = "这是谣言，别转发"
        explanation = "权威平台已就类似说法辟谣。" + clip(item.get("snippet", ""), 40)
        action = "不要转账、不要点链接，拨打96110" if danger else "别转发，告诉家里人也别信"
    elif ds_best:
        # 命中公开辟谣语料：确有辟谣记录，但不是政府网站原文 → 中风险 + 明确标注来源
        score, item = ds_best
        url = None
        evidence = clip(item.get("snippet", ""), 60)
        source_name = item.get("source") or "公开辟谣语料"
        risk = "中风险"
        conclusion = "这条已被辟谣过，别转发"
        explanation = ("公开辟谣记录里有这条说法，时间是 %s。"
                       "来源是微博社区辟谣，不是政府网站，建议再让子女核一遍。"
                       % (item.get("date") or "较早年份"))
        action = "别转发，告诉家里人也别信"
    elif live:
        url = live["url"]
        evidence = live["snippet"]
        source_name = live["source_name"]
        if danger:
            # 涉诈内容不因“查到页面”而降级
            risk = "高风险"
            conclusion = "这很像诈骗，先停一下别操作"
            explanation = "查到权威来源的相关说明。" + clip(live["snippet"], 36)
        elif live["tier"] == "media":
            # 权威媒体（新华网/科普中国等）：可信但非政府公告
            if live["debunk"]:
                risk = "中风险"
                conclusion = "媒体报道说这是不实说法"
                explanation = ("%s 的报道里提到这说法不实。" % live["source_name"]) + \
                              clip(live["snippet"], 30) + "以官方发布为准。"
            else:
                risk = "中风险"
                conclusion = "找到相关报道，未直接辟谣"
                explanation = ("%s 有相关报道，但没明确说真假，请您看原文再判断。"
                               % live["source_name"])
            action = "先看原文，重要的事再问官方"
        elif live["tier"] == "web":
            # 网络参考（百度知道/贴吧/百科/知乎等）：只提供线索，不是权威结论
            risk = "暂无权威结论"
            conclusion = "没找到官方说法，网上有讨论"
            explanation = ("只找到%s的说法，是网友讨论，不是官方结论，参考一下就好。"
                           % live["source_name"])
            action = "仅供参考，重要的事问官方渠道"
        elif live["debunk"]:
            risk = "高风险"
            conclusion = "这是谣言，别信也别用" if "健康" in cats else "这是谣言，别转发"
            explanation = "权威来源的原文明确说了这是不实说法。" + clip(live["snippet"], 36)
        else:
            risk = "中风险"
            conclusion = "查到权威说法，但没直接辟谣"
            explanation = "找到权威来源的页面，但没有明确说真假，请您对照原文再判断。"
        if live["tier"] not in ("media", "web"):
            action = ("不要转账、不要点链接，拨打96110" if danger else "先看官方原文，别急着转发")
    else:
        url = None
        evidence = None
        source_name = None
        if danger:
            # 规则：涉及转账/验证码/冒充公检法，风险等级至少为高风险（即使没查到原文）
            risk = "高风险"
            conclusion = "这很像诈骗，先停一下别操作"
            explanation = "没查到专门的辟谣原文，但这类要钱、要验证码的说法就是常见骗法。"
            action = "不要转账、不要点链接，拨打96110"
        else:
            risk = "暂无权威结论"
            conclusion = "暂时查不到官方说法，先别信"
            explanation = "我们的权威来源里没查到这条，不等于它是真的，先别照做。"
            action = "发给子女帮忙核实，或咨询官方渠道"

    # 出处内容概括：老人懒得点链接，直接把“里面说了什么”嚼碎喂给他
    source_summary = None
    detail = evidence
    if best:
        detail = best[1].get("snippet") or evidence
    elif ds_best:
        detail = ds_best[1].get("snippet") or evidence
    elif live:
        detail = live.get("full") or live.get("snippet") or evidence
    if detail and llm and llm.available() and len(detail) >= 15:
        try:
            source_summary = llm.summarize_source(detail, focus=claim)
        except Exception as e:
            print("[llm] 概括异常:", str(e)[:60])

    soft = None
    if not best and not live and not danger and llm and llm.available():
        # 没有权威依据时，给一句“仅供参考”的常识提醒（卡片里会标明不是官方结论）
        try:
            soft = llm.soft_hint(claim)
        except Exception as e:
            print("[llm] 提醒异常:", str(e)[:60])

    if "政策" in cats:
        explanation = clip(explanation + "以官方最新发布为准。", 80)

    if any(h in text for h in INJECTION_HINTS):
        explanation = clip(explanation + "这段话想让我改判断，本身就要警惕。", 80)

    voice = "%s。%s%s" % (
        conclusion,
        clip(explanation, 60),
        "想核实可以让子女帮忙，或者打96110。" if danger else "",
    )
    if url:
        voice += "点这里看官方原文。"
    voice = clip(voice, 120)

    share = clip("%s｜核查结论：%s%s" % (claim, conclusion,
                ("｜原文：" + url) if url else ""), 100)

    parent_note = clip("孩子转发的信息，陪他一起查一遍再信，比直接禁止管用。", 60) if "儿童" in cats else None

    # 来源等级：前端据此决定证据区块的措辞与样式
    if best:
        src_tier = "official"
    elif ds_best:
        src_tier = "dataset"
    elif live:
        src_tier = live.get("tier")
    else:
        src_tier = None

    return {
        "type": "card",
        "check_subject": claim,
        "risk_level": risk,
        "verdict": "no_evidence" if evidence is None else "evidence_found",
        "conclusion": clip(conclusion, 30),
        "explanation": clip(explanation, 80),
        "evidence": evidence,
        "source_summary": source_summary,
        "source_name": source_name,
        "source_url": url,
        "source_tier": src_tier,
        "action_advice": clip(action, 40),
        "voice_script": voice,
        "family_share_text": share,
        "parent_note": parent_note,
        "soft_hint": soft,
        "_debug": {
            "categories": cats,
            "kb_score": round(best[0], 3) if best else 0,
            "kb_title": best[1]["title"] if best else None,
            "matched": bool(best),
            "live_url": live["url"] if live else None,
            "live_debunk": live["debunk"] if live else None,
            "llm": bool(llm and llm.available()),
            "query": extra_q or None,
        },
    }


def need_clarify(text):
    t = re.sub(r"\s+", "", text or "")
    # 只有内容过短、完全看不出在说什么时才追问，避免反复打扰
    return len(t) < 6


def clarify_card():
    return {
        "type": "clarify",
        "question": "您想核实的是哪一类呢？",
        "options": ["保健品或药品", "钱和转账", "养老金等政策", "其他"],
    }


KB = load_kb()
if not KB:
    print("[WARN] 知识库为空：kb.json 与 kb_elderly.json 均未加载到条目；"
          "/api/check 将只能依赖联网检索（OFFLINE=1 时直接返回 no_evidence）。")


# ---------------------------------------------------------------- HTTP
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stdout.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), fmt % args))

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        STATIC = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/index.html": ("index.html", "text/html; charset=utf-8"),
            "/style.css": ("style.css", "text/css; charset=utf-8"),
            "/app.js": ("app.js", "application/javascript; charset=utf-8"),
            # 手机版（PWA）
            "/m": ("mobile.html", "text/html; charset=utf-8"),
            "/mobile": ("mobile.html", "text/html; charset=utf-8"),
            "/mobile.html": ("mobile.html", "text/html; charset=utf-8"),
            "/manifest.webmanifest": ("manifest.webmanifest", "application/manifest+json; charset=utf-8"),
            "/sw.js": ("sw.js", "application/javascript; charset=utf-8"),
            "/icon-192.png": ("icon-192.png", "image/png"),
            "/icon-512.png": ("icon-512.png", "image/png"),
        }
        if path in STATIC:
            name, ctype = STATIC[path]
            return self._file(name, ctype)
        if path == "/api/stats":
            return self._send(200, {"kb_items": len(KB), "whitelist": WHITELIST, "lan": _lan_urls()})
        if path == "/api/health":
            st = ocr.status() if ocr else {"provider": "none", "provider_label": "未启用"}
            return self._send(200, {
                "ok": True,
                "ocr": st,
                "llm": bool(llm and llm.available()),
                "kb_items": len(KB),
                "kb_source": KB_SOURCE,
                "offline": OFFLINE,
                "agent_configured": bool((os.environ.get("AGENT_BASE_URL") or "").strip()),
            })
        self._send(404, {"error": "not found"})

    def _file(self, name, ctype):
        p = os.path.join(HERE, name)
        if not os.path.exists(p):
            return self._send(404, "缺少文件：" + name, "text/plain; charset=utf-8")
        with open(p, "rb") as f:
            data = f.read()
        self._send(200, data, ctype)

    def _proxy(self):
        """POST /api/proxy：转发到 AgentArts 部署地址，地址与 token 只从环境变量读。"""
        base = (os.environ.get("AGENT_BASE_URL") or "").strip()
        token = (os.environ.get("AGENT_TOKEN") or "").strip()
        if not base:
            return self._send(503, {
                "type": "not_configured",
                "message": "未配置 AGENT_BASE_URL，代理未启用；本地降级请调用 /api/check",
            })
        p = urlparse(base)
        if p.scheme not in ("http", "https") or not p.hostname:
            return self._send(503, {
                "type": "not_configured",
                "message": "AGENT_BASE_URL 不是合法的 http/https 地址",
            })

        try:
            n = int(self.headers.get("Content-Length") or 0)
        except Exception:
            return self._send(400, {"type": "bad_request", "message": "bad content-length"})
        if n > PROXY_MAX_BYTES:
            return self._send(413, {"type": "too_large", "message": "payload exceeds 1 MB"})
        body = self.rfile.read(n) if n else b"{}"

        headers = {"Content-Type": self.headers.get("Content-Type")
                   or "application/json; charset=utf-8"}
        if token:
            headers["Authorization"] = "Bearer " + token
        req = urllib.request.Request(base, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=PROXY_TIMEOUT) as r:
                data = r.read()
                ctype = r.headers.get("Content-Type") or "application/json; charset=utf-8"
                return self._send(r.status, data, ctype)
        except urllib.error.HTTPError as e:
            try:
                data = e.read()
            except Exception:
                data = b""
            if not data:
                data = json.dumps({"type": "upstream_error", "status": e.code},
                                  ensure_ascii=False).encode("utf-8")
            ctype = (e.headers.get("Content-Type") if e.headers
                     else "application/json; charset=utf-8")
            return self._send(e.code, data, ctype)
        except urllib.error.URLError as e:
            if isinstance(e.reason, (socket.timeout, TimeoutError)):
                return self._send(504, {"type": "timeout", "message": "上游 8 秒未响应"})
            return self._send(502, {"type": "upstream_unreachable",
                                    "message": str(e.reason)[:120]})
        except (socket.timeout, TimeoutError):
            return self._send(504, {"type": "timeout", "message": "上游 8 秒未响应"})
        except Exception as e:
            return self._send(502, {"type": "upstream_unreachable", "message": str(e)[:120]})

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/proxy":
            return self._proxy()
        if path != "/api/check":
            return self._send(404, {"error": "not found"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        except Exception:
            return self._send(400, {"error": "bad json"})

        ocr_info = None
        text = (payload.get("text") or "").strip()

        # ---- 图片入口：拍照 / 截图 → 文字 → 走同一条核查链路
        raw_b64 = (payload.get("image") or "").strip()
        if raw_b64:
            if raw_b64.startswith("data:"):
                raw_b64 = raw_b64.split(",", 1)[-1]
            try:
                img = base64.b64decode(raw_b64, validate=False)
            except Exception:
                return self._send(400, {"error": "图片格式不对"})
            if len(img) > MAX_IMAGE_BYTES:
                return self._send(413, {"error": "图片太大，请压缩后再传"})
            if not img:
                return self._send(400, {"error": "图片是空的"})
            if ocr is None:
                return self._send(503, {"error": "服务端未安装 OCR 模块"})

            rec = ocr.extract(img)
            del img                      # 原图不留在内存里，也不落盘
            ocr_info = rec
            if not rec.get("text"):
                return self._send(200, {
                    "type": "ocr_failed",
                    "provider": rec.get("provider"),
                    "provider_label": (ocr.status() or {}).get("provider_label"),
                    "error": rec.get("error"),
                    "message": "图片里没认出字。可以拍清楚一点、把文字放大再试，"
                               "或者直接把消息贴到下面的框里。",
                })
            text = rec["text"]

        if not text:
            return self._send(400, {"error": "empty text"})
        if len(text) > 800:
            text = text[:800]

        if need_clarify(text):
            return self._send(200, clarify_card())

        card = build_card(text, KB)
        if ocr_info:
            card["ocr_text"] = text
            card["ocr_provider"] = ocr_info.get("provider")
            card["ocr_ms"] = ocr_info.get("ms")
        return self._send(200, card)


def _lan_urls(port=8765):
    """列出本机可能被手机访问到的地址"""
    ips = []
    try:
        out = socket.gethostbyname_ex(socket.gethostname())[2]
        ips += [i for i in out if not i.startswith("127.")]
    except Exception:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.append(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    seen, res = set(), []
    for ip in ips:
        if ip in seen:
            continue
        # 跳过回环、自动分配、Radmin VPN(26.x) 等手机连不上的地址
        if ip.startswith(("127.", "169.254.", "26.")):
            continue
        seen.add(ip)
        res.append("http://%s:%d/m" % (ip, port))
    return res


def main():
    port = 8765
    host = "0.0.0.0"          # 监听所有网卡，手机才能连
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    print("=" * 60)
    print("  银龄核查助手 · 本地服务")
    print("  知识库条目: %d" % len(KB))
    print("  白名单域名: %d 个" % len(WHITELIST))
    print("  本地模型: %s" % ("可用（Ollama）" if (llm and llm.available()) else "不可用（纯规则模式）"))
    print("  电脑打开: http://127.0.0.1:%d" % port)
    print("  手机打开: 见下面（需与电脑同一 Wi-Fi）")
    for u in _lan_urls(port):
        print("      %s" % u)
    print("=" * 60)
    if llm and llm.available():
        import threading
        threading.Thread(target=llm.warmup, daemon=True).start()
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
