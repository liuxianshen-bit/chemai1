/**
 * ChemAI Chat Widget — AI 化学助教对话组件
 *
 * 用法: 在 HTML 中加 <script src="./components/chat-widget.js"></script>
 * 自动在右下角创建浮动按钮，点击打开聊天面板。
 *
 * 支持:
 *   - SSE 流式输出（逐字显示）
 *   - 多轮对话（会话内保持上下文）
 *   - 打字指示器
 *   - 错误重连
 *   - 自适应移动端
 */

(function () {
  "use strict";

  // ============ 配置 ============
  const CONFIG = {
    persona: "tutor",           // tutor / teacher
    apiUrl: "/api/agent/chat/stream",
    title: "AI 化学助教",
    placeholder: "输入你的化学问题...",
    greeting: "你好！我是化学AI助教 🤖\n有什么化学问题可以问我哦～",
    maxHistory: 20,
  };

  // 如果是教师端
  if (window.location.pathname.includes("teacher")) {
    CONFIG.persona = "teacher";
    CONFIG.title = "AI 教研助手";
    CONFIG.placeholder = "输入教学问题...";
    CONFIG.greeting = "你好！我是AI教研助手 📊\n可以帮你分析学情、出题、查真题。";
  }

  // ============ DOM ============
  const style = document.createElement("style");
  style.textContent = `
.chemai-chat-btn{position:fixed;bottom:24px;right:24px;width:56px;height:56px;border-radius:50%;
background:linear-gradient(135deg,#6366f1,#8b5cf6);border:none;cursor:pointer;z-index:9999;
box-shadow:0 4px 16px rgba(99,102,241,.4);transition:transform .2s,box-shadow .2s;display:flex;
align-items:center;justify-content:center;font-size:24px;color:#fff}
.chemai-chat-btn:hover{transform:scale(1.08);box-shadow:0 6px 24px rgba(99,102,241,.5)}
.chemai-chat-btn:active{transform:scale(.95)}
.chemai-chat-panel{position:fixed;bottom:96px;right:24px;width:380px;max-width:calc(100vw-48px);
height:520px;max-height:calc(100vh-140px);background:#1e1e2e;border-radius:16px;z-index:9998;
box-shadow:0 8px 40px rgba(0,0,0,.4);display:none;flex-direction:column;overflow:hidden;
border:1px solid #313244}
.chemai-chat-panel.open{display:flex}
.chemai-chat-header{background:#181825;padding:14px 18px;display:flex;justify-content:space-between;
align-items:center;border-bottom:1px solid #313244}
.chemai-chat-header h3{margin:0;font-size:15px;color:#cdd6f4;font-weight:600}
.chemai-chat-close{background:none;border:none;color:#6c7086;font-size:20px;cursor:pointer;padding:0 4px}
.chemai-chat-close:hover{color:#cdd6f4}
.chemai-chat-messages{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:12px}
.chemai-msg{max-width:85%;padding:10px 14px;border-radius:12px;font-size:14px;line-height:1.6;
word-break:break-word;animation:chemai-fadein .3s}
.chemai-msg.user{align-self:flex-end;background:#6366f1;color:#fff;border-bottom-right-radius:4px}
.chemai-msg.assistant{align-self:flex-start;background:#313244;color:#cdd6f4;border-bottom-left-radius:4px}
.chemai-msg.error{align-self:flex-start;background:#3e1e2e;color:#f38ba8;font-size:13px}
.chemai-typing{align-self:flex-start;color:#6c7086;font-size:13px;padding:4px 14px;display:none}
.chemai-typing.show{display:block}
.chemai-chat-input{border-top:1px solid #313244;padding:12px;display:flex;gap:8px}
.chemai-chat-input textarea{flex:1;background:#313244;border:1px solid #45475a;border-radius:10px;
color:#cdd6f4;padding:10px 14px;font-size:14px;resize:none;min-height:44px;max-height:100px;
outline:none;font-family:inherit;line-height:1.4}
.chemai-chat-input textarea:focus{border-color:#6366f1}
.chemai-chat-send{background:linear-gradient(135deg,#6366f1,#8b5cf6);border:none;border-radius:10px;
color:#fff;padding:0 18px;cursor:pointer;font-size:14px;font-weight:500;white-space:nowrap}
.chemai-chat-send:hover{opacity:.9}
.chemai-chat-send:disabled{opacity:.5;cursor:not-allowed}
@keyframes chemai-fadein{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}}
@media(max-width:480px){.chemai-chat-panel{width:100vw;max-width:100vw;bottom:0;right:0;
border-radius:16px 16px 0 0;height:70vh;max-height:70vh}}
  `;
  document.head.appendChild(style);

  // 浮动按钮
  const btn = document.createElement("button");
  btn.className = "chemai-chat-btn";
  btn.innerHTML = "💬";
  btn.title = CONFIG.title;
  document.body.appendChild(btn);

  // 聊天面板
  const panel = document.createElement("div");
  panel.className = "chemai-chat-panel";
  panel.innerHTML = `
    <div class="chemai-chat-header">
      <h3>${CONFIG.title}</h3>
      <button class="chemai-chat-close">✕</button>
    </div>
    <div class="chemai-chat-messages" id="chemai-msgs">
      <div class="chemai-msg assistant">${CONFIG.greeting}</div>
    </div>
    <div class="chemai-typing" id="chemai-typing">AI 正在思考...</div>
    <div class="chemai-chat-input">
      <textarea id="chemai-input" placeholder="${CONFIG.placeholder}" rows="1"></textarea>
      <button class="chemai-chat-send" id="chemai-send">发送</button>
    </div>
  `;
  document.body.appendChild(panel);

  // ============ 状态 ============
  let isOpen = false;
  let isStreaming = false;
  let history = [];

  // ============ DOM 引用 ============
  const msgsEl = document.getElementById("chemai-msgs");
  const inputEl = document.getElementById("chemai-input");
  const sendBtn = document.getElementById("chemai-send");
  const typingEl = document.getElementById("chemai-typing");
  const closeBtn = panel.querySelector(".chemai-chat-close");

  // ============ 交互 ============
  btn.addEventListener("click", () => {
    isOpen = !isOpen;
    panel.classList.toggle("open", isOpen);
    if (isOpen) inputEl.focus();
  });

  closeBtn.addEventListener("click", () => {
    isOpen = false;
    panel.classList.remove("open");
  });

  inputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  // 自动调整输入框高度
  inputEl.addEventListener("input", () => {
    inputEl.style.height = "auto";
    inputEl.style.height = Math.min(inputEl.scrollHeight, 100) + "px";
  });

  sendBtn.addEventListener("click", sendMessage);

  // ============ 核心：发送消息 ============
  async function sendMessage() {
    const text = inputEl.value.trim();
    if (!text || isStreaming) return;

    inputEl.value = "";
    inputEl.style.height = "auto";
    isStreaming = true;
    sendBtn.disabled = true;

    // 显示用户消息
    addMessage("user", text);
    history.push({ role: "user", content: text });

    // 显示打字指示器
    showTyping(true);

    try {
      const token = getToken();
      const resp = await fetch(CONFIG.apiUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          persona: CONFIG.persona,
          message: text,
          provider: "deepseek",
          history: history.slice(0, -1), // 不含当前消息
        }),
      });

      if (!resp.ok) {
        const err = await resp.text();
        throw new Error(`HTTP ${resp.status}: ${err}`);
      }

      // SSE 流式读取
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let replyText = "";

      // 创建 assistant 消息气泡
      const bubble = addMessage("assistant", "");
      showTyping(false);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const data = line.slice(6);
            if (data === "[DONE]") continue;
            try {
              const chunk = JSON.parse(data);
              const delta =
                chunk.choices?.[0]?.delta?.content ||
                chunk.choices?.[0]?.message?.content ||
                "";
              if (delta) {
                replyText += delta;
                bubble.textContent = replyText;
                msgsEl.scrollTop = msgsEl.scrollHeight;
              }
            } catch {
              // 非 JSON chunk，跳过
            }
          }
        }
      }

      // 如果流式没有输出，回退到非流式
      if (!replyText) {
        bubble.remove();
        await fallbackNonStream(text);
        isStreaming = false;
        sendBtn.disabled = false;
        return;
      }

      history.push({ role: "assistant", content: replyText });
    } catch (err) {
      showTyping(false);
      addMessage("error", `请求失败: ${err.message}`);
    } finally {
      isStreaming = false;
      sendBtn.disabled = false;
      inputEl.focus();
    }
  }

  // ============ 辅助函数 ============
  function addMessage(role, text) {
    const el = document.createElement("div");
    el.className = `chemai-msg ${role}`;
    el.textContent = text;
    msgsEl.appendChild(el);
    msgsEl.scrollTop = msgsEl.scrollHeight;
    return el;
  }

  function showTyping(show) {
    typingEl.classList.toggle("show", show);
    msgsEl.scrollTop = msgsEl.scrollHeight;
  }

  function getToken() {
    try {
      const user = sessionStorage.getItem("chemai_user");
      if (user) {
        const parsed = JSON.parse(user);
        return parsed.token || "";
      }
    } catch {}
    return "";
  }

  async function fallbackNonStream(text) {
    try {
      const token = getToken();
      const resp = await fetch("/api/agent/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          persona: CONFIG.persona,
          message: text,
          provider: "deepseek",
          history: history.slice(0, -1),
        }),
      });

      if (resp.ok) {
        const data = await resp.json();
        const reply = data.content || "收到！";
        addMessage("assistant", reply);
        history.push({ role: "assistant", content: reply });
      } else {
        throw new Error(`HTTP ${resp.status}`);
      }
    } catch (err) {
      addMessage("error", `请求失败: ${err.message}`);
    }
  }

  console.log("[ChemAI] Chat widget loaded:", CONFIG.title);
})();
