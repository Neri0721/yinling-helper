"""
银龄核查助手 · 图片转文字（OCR）

三种来源，按可用性自动选择：
  1. huaweicloud  华为云通用文字识别（赛题二要求的云端能力，需 AK/SK）
  2. tesseract    本机装了 tesseract 时离线可用（走标准输入，不落临时文件）
  3. mock         都没有时返回示例文本，仅用于界面联调（前端会明确标注）

设计约束（与项目既有原则一致）：
  - 原图只在内存里过一遍，不落盘、不写日志、不进数据库；
  - 只把图片变成文字，不判断"图片是真是假"（那属于鉴伪，本项目不做也不用做）；
  - 返回前对卡号、身份证号、手机号、验证码打码。

环境变量：
  OCR_PROVIDER    auto | huaweicloud | tesseract | mock     默认 auto
  HUAWEI_AK       Access Key
  HUAWEI_SK       Secret Key
  HUAWEI_PROJECT_ID  项目 ID（控制台"我的凭证"里复制）
  HUAWEI_REGION  OCR 服务地域，默认 cn-north-4
  MOCK_OCR_TEXT  mock 模式下返回的文字（默认一句示例谣言）
"""

import hashlib
import hmac
import json
import os
import re
import shutil
import subprocess
import time
import urllib.parse
import urllib.request
from urllib.parse import quote

REQUEST_TIMEOUT = 20

MOCK_DEFAULT = "网传喝骨头汤能补钙，炖得越久钙越多，老人多喝还能防骨质疏松？"

# 敏感信息打码（只影响回显与日志，不影响核查逻辑）
PATTERNS = [
    ("idcard", re.compile(r"(?<!\d)(\d{6})\d{8}(\d{3}[\dXx])(?!\d)")),
    ("phone", re.compile(r"(?<!\d)(1[3-9]\d)\d{4}(\d{4})(?!\d)")),
    ("bankcard", re.compile(r"(?<!\d)(\d{6})\d{6,9}(\d{4})(?!\d)")),
    ("code", re.compile(r"(验证码|校验码|动态码)[^0-9]{0,4}(\d{4,6})")),
]


def mask_sensitive(text):
    """把卡号/身份证/手机号/验证码打码，其余原样保留"""
    if not text:
        return text
    out = text
    for kind, pat in PATTERNS:
        if kind == "code":
            out = pat.sub(lambda m: m.group(1) + " ****", out)
        else:
            out = pat.sub(lambda m: m.group(1) + "*" * 4 + m.group(2), out)
    return out


# ---------------------------------------------------------------- 华为云
def _hc_headers(method, url, body, ak, sk):
    """华为云 AK/SK 签名（SDK-HMAC-SHA256）"""
    p = urllib.parse.urlparse(url)
    canonical_uri = p.path or "/"
    qs = sorted(urllib.parse.parse_qsl(p.query, keep_blank_values=True))
    canonical_qs = "&".join(
        "%s=%s" % (quote(k, safe="-_.~"), quote(v, safe="-_.~")) for k, v in qs
    )
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    headers = {
        "content-type": "application/json",
        "host": p.hostname,
        "x-sdk-date": stamp,
    }
    signed = "content-type;host;x-sdk-date"
    canonical_headers = "".join(
        "%s:%s\n" % (k, headers[k].strip()) for k in sorted(headers)
    )
    creq = "\n".join(
        [
            method,
            canonical_uri,
            canonical_qs,
            canonical_headers,
            signed,
            hashlib.sha256(body).hexdigest(),
        ]
    )
    sts = "\n".join(
        ["SDK-HMAC-SHA256", stamp, hashlib.sha256(creq.encode("utf-8")).hexdigest()]
    )
    sig = hmac.new(sk.encode("utf-8"), sts.encode("utf-8"), hashlib.sha256).hexdigest()
    headers["Authorization"] = (
        "SDK-HMAC-SHA256 Access=%s, SignedHeaders=%s, Signature=%s" % (ak, signed, sig)
    )
    return headers


def _huaweicloud(image_bytes):
    ak = os.environ.get("HUAWEI_AK", "").strip()
    sk = os.environ.get("HUAWEI_SK", "").strip()
    pid = os.environ.get("HUAWEI_PROJECT_ID", "").strip()
    region = os.environ.get("HUAWEI_REGION", "cn-north-4").strip()
    if not (ak and sk and pid):
        raise RuntimeError("缺少 HUAWEI_AK / HUAWEI_SK / HUAWEI_PROJECT_ID")

    b64 = __import__("base64").b64encode(image_bytes).decode("ascii")
    body = json.dumps({"image": b64}).encode("utf-8")
    url = "https://ocr.%s.myhuaweicloud.com/v2/%s/ocr/general-text" % (region, pid)
    headers = _hc_headers("POST", url, body, ak, sk)
    headers["Host"] = urllib.parse.urlparse(url).hostname

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
        data = json.loads(r.read().decode("utf-8", "replace"))

    blocks = ((data.get("result") or {}).get("words_block_list")) or []
    lines = [b.get("words", "").strip() for b in blocks if b.get("words")]
    return [ln for ln in lines if ln]


# ---------------------------------------------------------------- tesseract
def _has_tesseract():
    return bool(shutil.which("tesseract"))


def _tesseract(image_bytes):
    """离线兜底：图片从标准输入喂进去，不产生临时文件"""
    cmd = ["tesseract", "-", "-", "-l", "chi_sim+eng", "--psm", "6"]
    p = subprocess.run(
        cmd, input=image_bytes, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        timeout=REQUEST_TIMEOUT,
    )
    text = p.stdout.decode("utf-8", "replace")
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


# ---------------------------------------------------------------- mock
def _mock(image_bytes):
    return [os.environ.get("MOCK_OCR_TEXT", MOCK_DEFAULT)]


# ---------------------------------------------------------------- 对外
def pick_provider():
    want = (os.environ.get("OCR_PROVIDER") or "auto").strip().lower()
    if want in ("huaweicloud", "tesseract", "mock"):
        return want
    if all(os.environ.get(k) for k in ("HUAWEI_AK", "HUAWEI_SK", "HUAWEI_PROJECT_ID")):
        return "huaweicloud"
    if _has_tesseract():
        return "tesseract"
    return "mock"


def extract(image_bytes, provider=None):
    """图片字节 → {text, lines, provider, ms, masked}

    不抛异常：任何失败都返回空文本 + 错误说明，由调用方决定怎么提示老人。
    """
    provider = provider or pick_provider()
    t0 = time.time()
    err = None
    lines = []
    try:
        if provider == "huaweicloud":
            lines = _huaweicloud(image_bytes)
        elif provider == "tesseract":
            lines = _tesseract(image_bytes)
        else:
            lines = _mock(image_bytes)
    except Exception as e:  # 网络、鉴权、超时都走这里
        err = str(e)[:160]
        print("[ocr] %s 失败: %s" % (provider, err))
        lines = []

    raw = "\n".join(lines).strip()
    return {
        "text": mask_sensitive(raw),
        "lines": [mask_sensitive(x) for x in lines],
        "provider": provider,
        "ms": int((time.time() - t0) * 1000),
        "chars": len(raw),
        "error": err,
    }


def status():
    """给 /api/health 和前端提示用"""
    p = pick_provider()
    return {
        "provider": p,
        "provider_label": {
            "huaweicloud": "华为云通用文字识别",
            "tesseract": "本机 tesseract（离线）",
            "mock": "演示模式（未接入 OCR）",
        }.get(p, p),
        "credentialed": bool(
            os.environ.get("HUAWEI_AK") and os.environ.get("HUAWEI_SK")
            and os.environ.get("HUAWEI_PROJECT_ID")
        ),
        "tesseract": _has_tesseract(),
    }


if __name__ == "__main__":
    print(json.dumps(status(), ensure_ascii=False, indent=2))
    sample = open(__file__, "rb").read(4096)
    r = extract(sample)
    print("provider=%s ms=%d chars=%d" % (r["provider"], r["ms"], r["chars"]))
    print("text:", (r["text"] or "")[:120])
    print("mask:", mask_sensitive("卡号 6222020200112233445 身份证 11010119900307123X 电话 13812345678 验证码是 668899"))
