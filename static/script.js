const setupPanel = document.getElementById("setup-panel");
const chatPanel = document.getElementById("chat-panel");
const setupForm = document.getElementById("setup-form");
const setupStatus = document.getElementById("setup-status");
const startBtn = document.getElementById("start-btn");
const chatTitle = document.getElementById("chat-title");
const messagesEl = document.getElementById("messages");
const chatForm = document.getElementById("chat-form");
const messageInput = document.getElementById("message-input");
const newChapterBtn = document.getElementById("new-chapter-btn");

let chatToken = null;

function setStatus(text, kind) {
  setupStatus.textContent = text;
  setupStatus.className = "status" + (kind ? " " + kind : "");
}

function addMessage(text, who) {
  const div = document.createElement("div");
  div.className = "msg " + who;
  div.innerHTML = text; // server only ever sends bold/<br>-formatted text
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

setupForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  startBtn.disabled = true;
  setStatus("Opening your chapter…");

  const payload = {
    student_class: document.getElementById("student_class").value,
    subject: document.getElementById("subject").value,
    chapter: document.getElementById("chapter").value,
  };

  try {
    const res = await fetch("/api/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();

    if (!res.ok) {
      setStatus(data.error || "Something went wrong.", "error");
      startBtn.disabled = false;
      return;
    }

    chatToken = data.chat_token;
    chatTitle.textContent = data.message;
    messagesEl.innerHTML = "";
    setupPanel.classList.add("hidden");
    chatPanel.classList.remove("hidden");
    messageInput.focus();
  } catch (err) {
    setStatus("Could not reach the server.", "error");
  } finally {
    startBtn.disabled = false;
  }
});

chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = messageInput.value.trim();
  if (!text) return;

  addMessage(text, "student");
  messageInput.value = "";
  messageInput.disabled = true;

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_token: chatToken, message: text }),
    });
    const data = await res.json();

    if (!res.ok) {
      addMessage(data.error || "Something went wrong.", "tutor");
    } else {
      addMessage(data.reply, "tutor");
    }
  } catch (err) {
    addMessage("Could not reach the server.", "tutor");
  } finally {
    messageInput.disabled = false;
    messageInput.focus();
  }
});

newChapterBtn.addEventListener("click", () => {
  chatToken = null;
  chatPanel.classList.add("hidden");
  setupPanel.classList.remove("hidden");
  setStatus("");
  setupForm.reset();
});
