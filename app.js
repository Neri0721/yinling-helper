/* 银龄核查助手 · 前端逻辑 */
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const input = $("input");
  const checkBtn = $("checkBtn");
  const placeholder = $("placeholder");
  const loading = $("loading");
  const loadingText = $("loadingText");
  const clarifyBox = $("clarifyBox");
  const card = $("card");
  const histList = $("historyList");

  const RISK_CLASS = { "高风险": "hi", "中风险": "mid", "低风险": "low", "暂无权威结论": "none" };
  const LS_KEY = "yinling.history.v1";
  const LS_FS = "yinling.fontsize";

  let lastCard = null;

  /* ---------------- 字号 ---------------- */
  const setFont = (px) => {
    px = Math.max(15, Math.min(22, px));
    document.documentElement.style.setProperty("--fs", px + "px");
    localStorage.setItem(LS_FS, String(px));
  };
  setFont(parseInt(localStorage.getItem(LS_FS) || "17", 10));
  $("fontPlus").onclick = () => setFont(parseInt(localStorage.getItem(LS_FS) || "17", 10) + 1);
  $("fontMinus").onclick = () => setFont(parseInt(localStorage.getItem(LS_FS) || "17", 10) - 1);

  /* ---------------- 步骤条 ---------------- */
  function setStep(n) {
    document.querySelectorAll(".step").forEach((el) => {
      const s = Number(el.dataset.step);
      el.classList.toggle("active", s === n);
      el.classList.toggle("done", s < n);
    });
  }

  /* ---------------- 视图切换 ---------------- */
  function show(which, text) {
    placeholder.hidden = which !== "placeholder";
    loading.hidden = which !== "loading";
    clarifyBox.hidden = which !== "clarify";
    card.hidden = which !== "card";
    if (text) loadingText.textContent = text;
  }

  /* ---------------- 历史 ---------------- */
  const loadHistory = () => {
    try { return JSON.parse(localStorage.getItem(LS_KEY) || "[]"); } catch { return []; }
  };
  const saveHistory = (list) => localStorage.setItem(LS_KEY, JSON.stringify(list.slice(0, 8)));

  function renderHistory() {
    histList.innerHTML = "";
    loadHistory().forEach((h) => {
      const li = document.createElement("li");
      const t = document.createElement("span");
      t.textContent = h.claim || h.text.slice(0, 18);
      const r = document.createElement("span");
      r.textContent = h.risk;
      li.append(t, r);
      li.onclick = () => { input.value = h.text; runCheck(); };
      histList.appendChild(li);
    });
  }
  $("clearHistory").onclick = () => { localStorage.removeItem(LS_KEY); renderHistory(); };

  /* ---------------- 渲染卡片 ---------------- */
  function renderCard(data) {
    lastCard = data;
    $("badge").textContent = data.risk_level;
    $("badge").className = "badge " + (RISK_CLASS[data.risk_level] || "none");
    $("subject").textContent = data.check_subject ? "核查对象：" + data.check_subject : "";
    $("conclusion").textContent = data.conclusion;
    $("explanation").textContent = data.explanation;

    const hasEvidence = !!data.evidence;
    $("evidenceBox").hidden = !hasEvidence;
    if (hasEvidence) {
      // 来源等级决定措辞：官方/语料/央媒/网络参考 必须区分清楚
      const label = $("evidenceBox").querySelector(".ev-label");
      const tier = data.source_tier;
      const LABELS = {
        official: "权威依据",
        dataset: "公开辟谣语料（非政府网站）",
        media: "媒体报道（非政府公告）",
        web: "网络参考 · 不是官方结论",
      };
      label.textContent = LABELS[tier] || "参考资料";
      $("evidenceBox").classList.toggle("is-weak", tier === "web" || tier === "dataset");

      // 优先显示“这段内容说了什么”的大白话概括；原文摘录退为细节
      const sumEl = $("sourceSummary");
      if (data.source_summary) {
        sumEl.hidden = false;
        sumEl.textContent = data.source_summary;
        $("evidence").classList.add("is-detail");
        $("evidence").textContent = "原文：“" + data.evidence + "”";
      } else {
        sumEl.hidden = true;
        $("evidence").classList.remove("is-detail");
        $("evidence").textContent = "“" + data.evidence + "”";
      }

      $("sourceName").textContent = data.source_name || "";
      const link = $("sourceLink");
      if (data.source_url) {
        link.href = data.source_url;
        link.hidden = false;
        link.textContent = tier === "web" ? "打开这个帖子 ↗" : "打开原文 ↗";
      } else {
        link.hidden = true;
      }
    }

    $("action").textContent = data.action_advice;

    // 查不到权威依据时，显示“常识提醒”，并明确标注不是官方结论
    const sf = $("softBox");
    if (data.soft_hint) {
      sf.hidden = false;
      $("softHint").textContent = data.soft_hint;
    } else {
      sf.hidden = true;
    }

    const pn = $("parentNote");
    if (data.parent_note) { pn.hidden = false; pn.textContent = "给家长的话：" + data.parent_note; }
    else pn.hidden = true;

    $("jsonOut").textContent = JSON.stringify(data, null, 2);
    show("card");
    setStep(3);
  }

  function renderClarify(data) {
    $("clarifyQuestion").textContent = data.question;
    const box = $("clarifyOptions");
    box.innerHTML = "";
    (data.options || []).forEach((opt) => {
      const b = document.createElement("button");
      b.textContent = opt;
      b.onclick = () => {
        input.value = (input.value.trim() || "我想核实：") + "（" + opt + "）";
        runCheck();
      };
      box.appendChild(b);
    });
    show("clarify");
    setStep(1);
  }

  /* ---------------- 朗读 ---------------- */
  function speak(text) {
    if (!("speechSynthesis" in window)) {
      alert("这个浏览器不支持朗读，文字内容已经显示在页面上。");
      return;
    }
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "zh-CN";
    u.rate = 0.92;
    u.pitch = 1;
    window.speechSynthesis.speak(u);
  }
  $("speakBtn").onclick = () => {
    if (!lastCard) return;
    speak(lastCard.voice_script || (lastCard.conclusion + "。" + lastCard.explanation));
  };

  /* ---------------- 自动朗读（默认开） ---------------- */
  const LS_AUTO = "yinling.autoread";
  let autoRead = localStorage.getItem(LS_AUTO) !== "0";

  function renderAutoBtn() {
    const b = $("btnAutoRead");
    b.textContent = autoRead ? "🔁 自动朗读：开" : "🔁 自动朗读：关";
    b.classList.toggle("on", autoRead);
    b.classList.toggle("off", !autoRead);
  }
  $("btnAutoRead").onclick = () => {
    autoRead = !autoRead;
    localStorage.setItem(LS_AUTO, autoRead ? "1" : "0");
    renderAutoBtn();
    if (!autoRead && "speechSynthesis" in window) window.speechSynthesis.cancel();
  };
  renderAutoBtn();

  function autoSpeak() {
    if (!autoRead || !lastCard) return;
    if (!("speechSynthesis" in window)) return;
    const text = lastCard.voice_script ||
      (lastCard.conclusion + "。" + (lastCard.explanation || ""));
    try {
      speak(text);
    } catch (e) {
      // 浏览器限制自动播放时，退回手动点“朗读”
      console.warn("自动朗读被拦截，请点喇叭按钮", e);
    }
  }

  /* ---------------- 复制转发 ---------------- */
  $("shareBtn").onclick = async () => {
    if (!lastCard) return;
    const text = lastCard.family_share_text || lastCard.conclusion;
    try {
      await navigator.clipboard.writeText(text);
      $("shareBtn").textContent = "✅ 已复制";
      setTimeout(() => ($("shareBtn").textContent = "📋 复制转给子女"), 1600);
    } catch {
      prompt("复制下面这段话发给子女：", text);
    }
  };

  $("againBtn").onclick = () => {
    input.value = "";
    input.focus();
    show("placeholder");
    setStep(1);
  };

  /* ---------------- 主流程 ---------------- */
  async function runCheck() {
    const text = input.value.trim();
    if (text.length < 2) {
      input.focus();
      return;
    }
    checkBtn.disabled = true;
    setStep(2);
    show("loading", "正在查权威来源…");
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    const t0 = Date.now();

    try {
      const res = await fetch("/api/check", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      const cost = Date.now() - t0;

      if (data.type === "clarify") {
        renderClarify(data);
      } else {
        renderCard(data);
        // 出卡片后自动朗读（老人不用再找按钮）
        autoSpeak();
        const list = loadHistory();
        list.unshift({
          text,
          claim: data.check_subject,
          risk: data.risk_level,
          time: Date.now(),
        });
        saveHistory(list);
        renderHistory();
      }
      loadingText.textContent = "用时 " + cost + " 毫秒";
    } catch (err) {
      show("placeholder");
      setStep(1);
      alert("核查失败：" + err.message + "\n请确认本地服务已启动（启动.bat）。");
    } finally {
      checkBtn.disabled = false;
    }
  }

  checkBtn.onclick = runCheck;
  input.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") runCheck();
  });
  $("clearBtn").onclick = () => {
    input.value = "";
    input.focus();
    show("placeholder");
    setStep(1);
  };
  document.querySelectorAll(".chip").forEach((c) => {
    c.onclick = () => { input.value = c.dataset.text; runCheck(); };
  });

  /* ---------------- 启动 ---------------- */
  renderHistory();
  setStep(1);
  fetch("/api/stats").then((r) => r.json()).then((s) => {
    $("kbInfo").textContent = "知识库：" + s.kb_items + " 条";
  }).catch(() => {});
})();
