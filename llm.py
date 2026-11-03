"""
本地大模型封装（Ollama）
- 全程免费、离线可用，不依赖任何云端 API、不需要 key、不需要实名
- 模型：qwen-ling（Qwen2.5-3B-Instruct Q4_K_M，约 2.1 GB）
- 只做三件事：抽取待核查主张 / 生成检索关键词 / 判断页面是否在辟谣
- 绝不生成"真假结论"，结论只能来自知识库原文 + 规则
"""

import json
import re
import time
import urllib.error
import urllib.request

OLLAMA = "http://127.0.0.1:11434"
MODEL = "qwen-ling"
TIMEOUT = 120

_warm = False


def available():
    try:
        with urllib.request.urlopen(OLLAMA + "/api/tags", timeout=3) as r:
            tags = json.loads(r.read().decode())
        return any(m.get("name", "").startswith(MODEL) for m in tags.get("models", []))
    except Exception:
        return False


def _post(path, payload, timeout=TIMEOUT):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(OLLAMA + path, data=data,
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def chat(prompt, system=None, temperature=0.1, max_tokens=200):
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    d = _post("/api/chat", {
        "model": MODEL,
        "messages": msgs,
        "stream": False,
        "keep_alive": "30m",          # 常驻显存，避免每次都冷启动
        "options": {"temperature": temperature, "num_predict": max_tokens},
    })
    return (d.get("message") or {}).get("content", "").strip()


def warmup():
    """服务启动时预热，避免第一位老人等一分钟"""
    global _warm
    if _warm:
        return
    try:
        chat("你好", max_tokens=8)
        _warm = True
        print("[llm] 模型已预热")
    except Exception as e:
        print("[llm] 预热失败:", str(e)[:80])


# ---------------------------------------------------------------- 任务封装
CLAIM_SYSTEM = (
    "你是文本抽取工具。把用户的话压缩成一个待核查的说法，"
    "必须保留原话的意思，不能改变肯定或否定的方向。只输出这个说法，不要解释。"
)
CLAIM_FEWSHOT = """示例：
输入：群里说喝骨头汤能补钙是真的吗
输出：喝骨头汤能补钙
输入：我妈说隔夜菜吃了会中毒，真的假的
输出：隔夜菜吃了会中毒
输入：有人打电话说我账户涉嫌洗钱要转安全账户
输出：账户涉嫌洗钱要转安全账户
"""


def extract_claim(text, fallback=""):
    prompt = CLAIM_FEWSHOT + "\n输入：" + text + "\n输出："
    try:
        out = chat(prompt, system=CLAIM_SYSTEM, max_tokens=40)
        out = re.sub(r"^(输出[:：]?)", "", out).strip().strip("。，,.")
        out = out.split("\n")[0].strip()
        if 2 <= len(out) <= 40:
            return out
    except Exception as e:
        print("[llm] 抽取失败:", str(e)[:60])
    return fallback


KW_SYSTEM = "你是检索词生成工具。只输出关键词，用空格分隔，不要标点，不要解释。"
KW_FEWSHOT = """示例：
输入：我妈说隔夜菜吃了会中毒
输出：隔夜菜 中毒
输入：喝骨头汤能不能补钙
输出：骨头汤 补钙
"""


def search_keywords(text, fallback=""):
    prompt = KW_FEWSHOT + "\n输入：" + text + "\n输出："
    try:
        out = chat(prompt, system=KW_SYSTEM, max_tokens=30)
        out = out.split("\n")[0].strip()
        out = re.sub(r"[，,。；;：:\"'（）()]", " ", out)
        out = re.sub(r"\s+", " ", out).strip()
        if 2 <= len(out) <= 40:
            return out
    except Exception as e:
        print("[llm] 关键词失败:", str(e)[:60])
    return fallback


DEBUNK_SYSTEM = (
    "你是文本分类工具。判断给定文字是否在辟谣（说明某个说法是假的、不实的）。"
    "只回答两个字之一：辟谣 或 不是。"
)


def is_debunking(passage):
    try:
        out = chat("文字：" + passage[:600] + "\n回答：", system=DEBUNK_SYSTEM, max_tokens=8)
        return "辟谣" in out
    except Exception as e:
        print("[llm] 判读失败:", str(e)[:60])
        return None


MATCH_SYSTEM = (
    "你是核对工具。【记录】里辟谣的传言，是否与【问题】讨论的是同一个传言、或同一类说法？"
    "只回答一个字：是 或 否。"
)


def same_topic(claim, record, max_tokens=6):
    """防假阳性：确认知识库条目和用户问的是同一件事"""
    try:
        out = chat("【问题】" + claim + "\n【已有辟谣记录】" + record[:200] + "\n回答：",
                   system=MATCH_SYSTEM, max_tokens=max_tokens)
        out = out.strip()
        if out.startswith("是"):
            return True
        if out.startswith("否"):
            return False
    except Exception as e:
        print("[llm] 复核失败:", str(e)[:60])
    return None


SUMMARIZE_SYSTEM = (
    "你是给中老年人转述内容的助手。用一句大白话说明这段文字主要讲了什么、为什么这么说，"
    "15到40个字，像跟家里老人聊天。不要出现英文、缩写、专业术语和具体数字，"
    "不要写半截话，不要加你自己的判断。"
    "如果这段文字里还提到别的东西，只说跟老人问的那件事有关的部分。"
)


def summarize_source(passage, focus=None, max_len=45):
    """把链接页面的内容压成一句大白话（老人不用点进去看）
    focus: 用户问的那句话，用来只概括相关部分
    """
    p = (passage or "").strip()
    if len(p) < 10:
        return None
    try:
        if focus:
            prompt = ("【老人在问】" + focus + "\n【这段文字】" + p[:500] +
                      "\n用一句话说这段文字里跟这个问题有关的内容、为什么：")
        else:
            prompt = "【这段文字】" + p[:500] + "\n用一句话说明它讲了什么、为什么："
        out = chat(prompt, system=SUMMARIZE_SYSTEM, max_tokens=90)
        out = out.split("\n")[0].strip().strip("。")
        out = re.sub(r"^(这段文字|概括|一句话概括|它说)[:：]?", "", out).strip()
        if len(out) < 12:
            return None
        return out if len(out) <= max_len else out[:max_len - 1] + "…"
    except Exception as e:
        print("[llm] 概括失败:", str(e)[:60])
    return None


SOFT_SYSTEM = (
    "你是给中老年人解释事情的助手。用大白话给一句提醒，不超过40字，"
    "不要下'真的/假的'结论，只给谨慎建议。"
)


def soft_hint(text):
    """查不到权威依据时，给一句'仅供参考'的常识提醒（卡片里会明确标注非官方）"""
    try:
        out = chat("这句话：" + text + "\n给出提醒：", system=SOFT_SYSTEM, max_tokens=60)
        out = out.split("\n")[0].strip().strip("。")
        if 4 <= len(out) <= 45:
            return out
    except Exception as e:
        print("[llm] 提醒失败:", str(e)[:60])
    return None


if __name__ == "__main__":
    print("可用:", available())
    t0 = time.time()
    print("主张:", extract_claim("群里说喝骨头汤能补钙是真的吗"))
    print("关键词:", search_keywords("我妈说隔夜菜吃了会中毒，这是真的吗"))
    print("判读:", is_debunking("网传喝骨头汤能补钙是谣言，骨头里的钙很难溶进汤里。"))
    print("提醒:", soft_hint("喝骨头汤能补钙"))
    print("总耗时 %.1f 秒" % (time.time() - t0))
