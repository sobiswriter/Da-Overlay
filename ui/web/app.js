/* Local UI. Only the desktop bridge talks to Gemini or reads the machine. */
"use strict";
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const escapeHTML = value => String(value ?? "").replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
const icon = name => `<i data-lucide="${name}"></i>`;
const mark = '<svg aria-hidden="true"><use href="#cutex-mark"/></svg>';
let state = null;
let view = "chat";
let toastTimer;
let captureBusy = false;
let recordingActionPending = false;
let commandIndex = 0;
let autoScroll = true;
let lastSession = null;
let visibleMessageLimit = 80;
let originalPersonas = null;
const connectionBannerHTML = $("#connection-banner").innerHTML;
const modeDescriptions = {
  companion: "A curious mind, a familiar presence.",
  focus: "Less friction. A little more progress.",
  study: "Let’s make the complicated click.",
  play: "Good company for the side quest.",
};
const presets = [
  { name: "Anna", icon: "orbit", description: "Warm, curious, quietly capable.", persona: "You are Anna, a warm, perceptive desktop companion. Be curious, candid, and practical. Match the user's energy. Have a sense of humor without forcing it. Be a thoughtful friend who can also help untangle difficult work." },
  { name: "TARS", icon: "bot", description: "Dry wit. Very good instincts.", persona: "You are TARS, a reliable companion with dry humor and direct, practical intelligence. Be concise, loyal, and refreshingly honest. Make the occasional deadpan joke without getting in the way of helping." },
  { name: "Holmes", icon: "search", description: "Observant, precise, a little witty.", persona: "You are Holmes, a perceptive and thoughtful companion. Be precise, curious, and gently witty. Distinguish evidence from assumptions. Help the user reason through difficult situations without sounding pompous." },
  { name: "Neko", icon: "cat", description: "Playful energy. A softer landing.", persona: "You are Neko, a playful, kind, and attentive companion. Be lively without overdoing it. Offer a softer landing after a long day, and be clear and capable when the user needs practical help." },
];

function icons(root = document) {
  if (window.lucide) lucide.createIcons({ root, attrs: { "aria-hidden": "true" } });
}

function toast(text, error = false) {
  const node = $("#toast");
  clearTimeout(toastTimer);
  node.innerHTML = `${icon(error ? "circle-alert" : "check")}${escapeHTML(text)}`;
  node.classList.toggle("error", error);
  node.hidden = false;
  icons(node);
  toastTimer = setTimeout(() => { node.hidden = true; }, error ? 8500 : 4000);
}

async function call(action, data = {}, quiet = false) {
  if (!window.pywebview?.api) {
    if (!quiet) toast("Open Cutex through main.py or the desktop launcher to use this control.", true);
    return null;
  }
  try {
    const response = await window.pywebview.api.dispatch(action, data);
    if (!response?.ok) {
      if (!quiet) toast(response?.error || "That action could not be completed.", true);
      return null;
    }
    return response.data == null ? true : response.data;
  } catch (error) {
    if (!quiet) toast("The desktop connection was interrupted. Please reopen Cutex.", true);
    return null;
  }
}

function activeSession() {
  return state?.sessions.find(session => session.id === state.active_session);
}

function markdown(text) {
  const rendered = window.marked ? marked.parse(text, { gfm: true, breaks: true }) : escapeHTML(text);
  return DOMPurify.sanitize(rendered, {
    FORBID_TAGS: ["img", "style", "script", "iframe", "form", "input", "button", "video", "audio", "svg", "math"],
    FORBID_ATTR: ["style", "srcset", "id", "name"],
    ALLOW_DATA_ATTR: false,
  });
}

function localTime(value) {
  try { return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); }
  catch { return ""; }
}

function localDate(value) {
  try { return new Date(value).toLocaleDateString([], { month: "short", day: "numeric" }); }
  catch { return ""; }
}

function renderSessions() {
  const query = $("#session-search").value.trim().toLowerCase();
  const sessions = [...state.sessions].sort((a, b) => b.updated_at.localeCompare(a.updated_at));
  const filtered = sessions.filter(session => !query || session.title.toLowerCase().includes(query)
    || session.messages.some(message => message.text.toLowerCase().includes(query)));
  $("#sessions").innerHTML = filtered.length ? filtered.map(session => `
    <button class="session-item ${session.id === state.active_session ? "active" : ""}" data-session="${escapeHTML(session.id)}" title="${escapeHTML(session.title)}" ${session.id === state.active_session ? 'aria-current="true"' : ""}>
      ${icon("message-square")}<span>${escapeHTML(session.title)}</span>
    </button>`).join("") : `<p class="session-empty">${query ? "No conversations match that thought." : "Your conversations will feel at home here."}</p>`;
  icons($("#sessions"));
}

function renderMessage(message, isLast) {
  const user = message.role === "user";
  const streaming = message.status === "streaming";
  const hiddenProactive = streaming && message.proactive;
  if (hiddenProactive) return "";
  const label = user ? "You" : message.persona_name || state.settings.persona_name;
  const content = user ? escapeHTML(message.text) : markdown(message.text);
  const thinking = streaming && !message.text;
  const sources = (message.sources || []).map((source, index) => {
    if (!/^https?:\/\//i.test(source.url)) return "";
    return `<a class="source-link" href="${escapeHTML(source.url)}" title="${escapeHTML(source.title)}">${icon("arrow-up-right")}<span>${index + 1}. ${escapeHTML(source.title)}</span></a>`;
  }).join("");
  let suggestions = "";
  if (message.search_suggestions) {
    suggestions = DOMPurify.sanitize(message.search_suggestions, {
      ALLOWED_TAGS: ["div", "span", "a", "p", "ul", "li"], ALLOWED_ATTR: ["href", "title"],
    });
  }
  return `<article class="message ${user ? "user" : "model"} ${streaming && !thinking ? "streaming" : ""}" data-message-id="${escapeHTML(message.id)}">
    <div class="message-header">${user ? "" : mark}<strong>${escapeHTML(label)}</strong><time datetime="${escapeHTML(message.created_at)}">${localTime(message.created_at)}</time>${message.mode && !user ? `<span class="mode-badge">${escapeHTML(message.proactive ? "A LITTLE THOUGHT" : message.mode.toUpperCase())}</span>` : ""}</div>
    <div class="message-content">${message.voice_duration ? `<span class="voice-badge">${icon("mic")}Voice · ${Math.round(message.voice_duration)}s${message.voice_transcribed ? " · transcribed" : ""}</span>` : ""}${thinking ? '<div class="thinking"><span></span><span></span><span></span><small>A thought is taking shape…</small></div>' : content}</div>
    ${message.capture ? `<div class="capture-label">${icon("scan")}Screen shared for this message</div>` : ""}
    ${message.error ? `<div class="message-error">${escapeHTML(message.error)}</div>` : ""}
    ${message.status === "stopped" ? '<div class="message-notice">Stopped. Your partial response is saved.</div>' : ""}
    ${message.notice ? `<div class="message-notice">${escapeHTML(message.notice)}</div>` : ""}
    ${sources ? `<div class="sources" aria-label="Sources">${sources}</div>` : ""}
    ${suggestions ? `<div class="search-suggestions">${suggestions}</div>` : ""}
    ${!user && !streaming ? `<div class="message-actions">${message.text ? `<button data-copy-message="${escapeHTML(message.id)}" title="Copy response">${icon("copy")}Copy</button><button data-remember-message="${escapeHTML(message.id)}" title="Save response as a memory">${icon("bookmark")}Remember</button><button data-action="read-message" data-message="${escapeHTML(message.id)}" title="Read reply aloud">${icon("volume-2")}Listen</button>` : ""}${isLast ? `<button data-action="retry" title="Regenerate the last response">${icon("rotate-ccw")}Try again</button>` : ""}</div>` : ""}
  </article>`;
}

function nearBottom() {
  const node = $("#conversation-scroll");
  return node.scrollHeight - node.scrollTop - node.clientHeight < 100;
}

function scrollBottom(force = false) {
  if (force || autoScroll) requestAnimationFrame(() => {
    const node = $("#conversation-scroll");
    node.scrollTop = node.scrollHeight;
  });
}

function renderMessages() {
  const session = activeSession();
  const messages = (session?.messages || []).filter(message => !message.hidden);
  const changedSession = lastSession !== session?.id;
  if (changedSession) { autoScroll = true; lastSession = session?.id; visibleMessageLimit = 80; }
  $("#welcome").hidden = messages.length > 0;
  $("#messages").hidden = !messages.length;
  const visible = messages.slice(-visibleMessageLimit);
  const earlier = messages.length - visible.length;
  $("#messages").innerHTML = (earlier ? `<button class="load-earlier secondary-button" data-action="load-earlier">${icon("history")}Show earlier messages (${earlier})</button>` : "")
    + visible.map((message, index) => renderMessage(message, index === visible.length - 1)).join("");
  icons($("#messages"));
  scrollBottom(changedSession);
}

function renderMemories() {
  const memories = state.memories;
  const enabled = memories.filter(memory => memory.enabled).length;
  $("#memory-count").textContent = memories.length;
  $("#composer-memory-count").textContent = enabled ? `${enabled} ${enabled === 1 ? "memory" : "memories"}` : "Memory";
  $("#library-summary").textContent = `${memories.length} ${memories.length === 1 ? "memory" : "memories"} · ${enabled} in context`;
  $("#memory-list").innerHTML = memories.length ? memories.map(memory => `
    <article class="memory-row ${memory.enabled ? "" : "disabled"}"><div class="memory-row-top">${icon("notebook-pen")}<h3>${escapeHTML(memory.title)}</h3><time>${localDate(memory.created_at)}</time></div><p>${escapeHTML(memory.text)}</p><div class="memory-row-bottom"><label class="memory-toggle"><input type="checkbox" data-memory-toggle="${escapeHTML(memory.id)}" ${memory.enabled ? "checked" : ""}><span class="switch" aria-hidden="true"></span><span>${memory.enabled ? "In context" : "Kept private"}</span></label><button class="icon-button tiny" data-delete-memory="${escapeHTML(memory.id)}" title="Delete this memory" aria-label="Delete ${escapeHTML(memory.title)}">${icon("trash-2")}</button></div></article>
  `).join("") : `<div class="library-empty">${icon("notebook-pen")}<h3>Every connection starts somewhere.</h3><p>A favorite thing. A project you’re working on. A detail you’d like to keep. Give your companion a little context that lasts.</p><button class="primary-button" data-action="add-memory">${icon("plus")}Keep your first memory</button></div>`;
  icons($("#memory-list"));
}

function fillPersona() {
  editingCompanionId = state.active_companion;
  draftAvatar = state.settings.persona_avatar || "";
  $("#persona-name").value = state.settings.persona_name;
  $("#persona-instructions").value = state.settings.persona;
  $("#persona-form").dataset.dirty = "false";
  renderPresets();
  renderAvatar();
}

let editingCompanionId = null;
let draftAvatar = "";
function avatarHTML(avatar) {
  return avatar ? `<img src="${escapeHTML(avatar)}" alt="">` : '<svg aria-hidden="true"><use href="#orbital"/></svg>';
}
function renderAvatar() {
  $("#avatar-preview").innerHTML = avatarHTML(draftAvatar);
  $("#companion-save-hint").textContent = editingCompanionId ? "Changes apply to this saved companion. Conversations stay intact." : "Save a new companion. Your other companions stay as they are.";
}
function renderCompanions() {
  $("#saved-companions").innerHTML = (state.companions || []).map(c => `<div class="saved-companion ${c.id === state.active_companion ? "active" : ""}"><button type="button" data-companion="${escapeHTML(c.id)}" aria-pressed="${c.id === state.active_companion}"><span class="companion-avatar">${avatarHTML(c.avatar)}</span><span><strong>${escapeHTML(c.name)}</strong><small>${c.id === state.active_companion ? "With you now" : "Switch companion"}</small></span></button>${c.id !== state.active_companion ? `<button type="button" class="remove-companion" data-delete-companion="${escapeHTML(c.id)}" aria-label="Remove ${escapeHTML(c.name)}">${icon("x")}</button>` : ""}</div>`).join("");
  $(".companion-card .mini-orb").innerHTML = avatarHTML(state.settings.persona_avatar);
  icons($("#saved-companions"));
}
function avatarCanvas() {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 96;
  const context = canvas.getContext("2d");
  context.beginPath(); context.arc(48, 48, 48, 0, Math.PI * 2); context.clip();
  return { canvas, context };
}

function renderPresets() {
  $("#persona-presets").innerHTML = presets.map((preset, index) => `
    <button class="persona-preset ${$("#persona-name").value === preset.name ? "active" : ""}" data-preset="${index}">${icon(preset.icon)}<span><strong>${preset.name}</strong><small>${preset.description}</small></span></button>`).join("");
  icons($("#persona-presets"));
}

function renderContext() {
  const settings = state.settings;
  $$("[data-setting]").forEach(input => { input.checked = settings[input.dataset.setting]; });
  const context = $("#context-state");
  if (state.attachment) {
    context.innerHTML = `<span class="context-state-icon">${icon("scan-eye")}</span><strong>Ready for a fresh pair of eyes.</strong><p>Your capture is attached.<br>Only shared when you send.</p>`;
  } else if (settings.share_context && state.context) {
    context.innerHTML = `<span class="context-state-icon">${icon("app-window")}</span><strong>Window context is on.</strong><p>${escapeHTML(state.context)}</p>`;
  } else if (settings.share_context) {
    context.innerHTML = `<span class="context-state-icon">${icon("app-window")}</span><strong>A little more in the loop.</strong><p>Your app name and title will be<br>included with your next message.</p>`;
  } else {
    context.innerHTML = `<span class="context-state-icon">${icon("monitor")}</span><strong>Just us, for now.</strong><p>Share a screen when you’d like<br>another pair of eyes.</p>`;
  }
  const observing = settings.autopilot_enabled && !state.autopilot_paused;
  $("#privacy-note").textContent = observing && settings.autopilot_screenshots ? "Autopilot sees periodic snapshots · Alt Shift P to pause." : settings.capture_mode !== "off" ? `Auto-attach: ${settings.capture_mode === "screen" ? "primary screen" : "region selection"} on every send · Alt 0 to change.` : settings.share_context ? "Window titles shared. Manual captures send with your message." : "Your screen stays yours until you share it.";
  $("#proactive-description").textContent = settings.autopilot_screenshots ? "Periodic screen check-ins, on your terms. No audio. No continuous recording." : "A thought when your activity changes. Enable screen snapshots in Settings for visual awareness.";
  $("#proactive-state").innerHTML = `<span class="${observing ? "status-dot" : "small-ring"}"></span>${state.autopilot_paused ? "Paused · check your Gemini connection" : observing ? `Checking in · every ${Math.round(settings.autopilot_interval / 60)} min` : "Quiet until you need me"}`;
  $(".capture-button>span").textContent = settings.capture_mode === "off" ? "Share screen" : `Auto: ${settings.capture_mode === "screen" ? "screen" : "region"}`;
  $("#mode-description").textContent = modeDescriptions[settings.mode];
  const preview = $("#attachment-preview");
  preview.hidden = !state.attachment;
  if (state.attachment) {
    preview.innerHTML = `<img src="${state.attachment.data_url}" alt="Preview of the screen capture to send"><div><strong>${state.attachment.kind === "region" ? "A little piece of your screen" : "Your primary screen"}</strong><small>${state.attachment.width} × ${state.attachment.height} · Sent with your next message only</small></div><button type="button" class="icon-button" data-action="clear-attachment" aria-label="Remove screen capture" title="Remove capture">${icon("x")}</button>`;
  } else preview.innerHTML = "";
  icons(context);
  icons(preview);
}

let voiceLayout = "";
function renderVoice() {
  const voice = state?.voice || {};
  const active = !!voice.active, draft = voice.draft_seconds != null, speaking = !!voice.speaking;
  const button = $("#record-button");
  if (button.dataset.recording !== String(active)) {
    button.dataset.recording = String(active);
    button.innerHTML = icon(active ? "square" : "mic");
    button.setAttribute("aria-label", active ? "Stop recording voice" : "Record a voice message");
    button.setAttribute("aria-pressed", String(active));
    button.classList.toggle("recording", active); icons(button);
  }
  button.disabled = (!!state?.busy && !active) || recordingActionPending;
  button.setAttribute("aria-busy", String(recordingActionPending));
  $("#send-button").disabled = active;
  $("#mute-button").hidden = !speaking;
  const node = $("#voice-draft");
  node.hidden = !active && !draft;
  node.setAttribute("aria-live", active ? "off" : "polite");
  node.classList.toggle("recording", active);
  node.style.setProperty("--voice-level", Math.max(0, Math.min(1, voice.level || 0)));
  const layout = `${active}:${draft}`;
  if (layout !== voiceLayout) {
    voiceLayout = layout;
    node.innerHTML = `<span class="voice-wave" aria-hidden="true"><span></span><span></span><span></span><span></span><span></span></span><span class="voice-copy"><strong id="voice-title"></strong><small>${active ? "Only recording now · 2 minute limit" : "Sent to Google only when you press Send"}</small></span>${active ? `<button type="button" class="secondary-button" data-action="record">Stop</button><button type="button" class="icon-button" data-action="cancel-recording" aria-label="Cancel recording">${icon("x")}</button>` : `<button type="button" class="icon-button" data-action="play-voice" title="Play voice message" aria-label="Play voice message">${icon("play")}</button><button type="button" class="icon-button" data-action="clear-voice" aria-label="Discard voice message">${icon("x")}</button>`}`;
    icons(node);
    if (active) $("#live-status").textContent = "Recording started. Stop to review your voice message.";
    else if (draft) $("#live-status").textContent = "Voice message ready to review and send.";
  }
  const seconds = Math.floor(active ? voice.seconds || 0 : voice.draft_seconds || 0);
  const title = `${active ? "Recording" : "Voice message"} · ${Math.floor(seconds/60)}:${String(seconds%60).padStart(2,"0")}`;
  if ($("#voice-title").textContent !== title) $("#voice-title").textContent = title;
  if (voice.warning) $(".voice-copy small", node).textContent = "Some audio was skipped. Review or record again.";
}

function render() {
  if (!state) return;
  document.documentElement.dataset.theme = state.settings.theme;
  document.body.classList.toggle("compact", state.overlay);
  const session = activeSession();
  $("#page-title").textContent = view === "chat" ? session?.title || "New conversation" : view === "memories" ? "Your memories" : "Your companion";
  $$(".persona-name").forEach(node => { node.textContent = state.settings.persona_name; });
  $("#overlay-label").textContent = state.overlay ? "Open workspace" : "Open overlay";
  $$("[data-action='pin']").forEach(button => button.setAttribute("aria-pressed", String(state.settings.on_top || state.overlay)));
  $("#connection-banner").hidden = state.settings.connection_ready;
  $("#model-label").textContent = state.settings.model.replace(/^gemini-/, "Gemini ").replace(/-preview$/, "").replace(/-/g, " ");
  $("#companion-status").textContent = state.busy ? state.busy_kind === "memory" ? "Keeping a little memory…" : "A thought is taking shape…" : "Ready when you are";
  $("#send-button").hidden = state.busy;
  $("#stop-button").hidden = !state.busy;
  $("#prompt").setAttribute("aria-busy", String(state.busy));
  $$("[data-mode]").forEach(button => {
    button.classList.toggle("active", button.dataset.mode === state.settings.mode);
    button.setAttribute("aria-pressed", String(button.dataset.mode === state.settings.mode));
  });
  $("#save-status").textContent = state.save_error ? "Not saved · export a copy" : state.busy ? "Saving as we go…" : "Saved on this device";
  $("#save-status").style.color = state.save_error ? "var(--danger)" : "";
  renderSessions();
  renderMessages();
  renderMemories();
  renderContext();
  renderVoice();
  renderCompanions();
  if ($("#persona-form").dataset.dirty !== "true") fillPersona();
}

function switchView(next) {
  if (!["chat", "memories", "companion"].includes(next)) return;
  view = next;
  $$(".view").forEach(node => { node.hidden = node.id !== `view-${view}`; });
  $$(".nav-item").forEach(node => {
    node.classList.toggle("active", node.dataset.view === view);
    if (node.dataset.view === view) node.setAttribute("aria-current", "page");
    else node.removeAttribute("aria-current");
  });
  if (state) render();
  if (next === "companion") loadOriginalPersonas();
  closePopovers();
}

async function loadOriginalPersonas() {
  if (originalPersonas) return;
  const result = await call("personas");
  if (result && typeof result === "object") {
    originalPersonas = result;
    $("#original-personas").innerHTML = '<option value="">Choose from your original persona library…</option>'
      + Object.keys(result).map(name => `<option value="${escapeHTML(name)}">${escapeHTML(name)}</option>`).join("");
  }
}

function openDialog(id) {
  closePopovers();
  const dialog = $(`#${id}`);
  if (!dialog.open) dialog.showModal();
}

function closePopovers() { $$(".popover").forEach(node => { node.hidden = true; }); }

function togglePopover(id, button) {
  const popover = $(`#${id}`);
  const wasOpen = !popover.hidden;
  closePopovers();
  if (wasOpen) return;
  popover.hidden = false;
  const rect = button.getBoundingClientRect();
  popover.style.left = `${Math.max(8, Math.min(rect.left, window.innerWidth - popover.offsetWidth - 10))}px`;
  const above = rect.top > window.innerHeight / 2;
  popover.style.top = `${above ? rect.top - popover.offsetHeight - 8 : rect.bottom + 8}px`;
  $("button", popover)?.focus();
}

function openSettings() {
  if (!state) return;
  $("#api-key").value = "";
  $("#key-status").textContent = state.settings.key_present ? "Connected · key protected by Windows" : "Not connected";
  $("#model-input").value = state.settings.model;
  $("#provider-input").value = state.settings.provider;
  $("#vertex-project").value = state.settings.vertex_project;
  $("#vertex-location").value = state.settings.vertex_location;
  $("#vertex-account").value = state.settings.vertex_account;
  $("#voice-replies").checked = state.settings.voice_replies;
  $("#connection-status").textContent = "";
  $("#cloud-fields").hidden = state.settings.provider !== "vertex";
  $("#key-form").hidden = state.settings.provider === "vertex";
  $("#opacity-input").value = Math.round(state.settings.opacity * 100);
  $("#opacity-value").textContent = `${Math.round(state.settings.opacity * 100)}%`;
  if (![...$("#autopilot-interval").options].some(option => Number(option.value) === state.settings.autopilot_interval)) {
    $("#autopilot-interval").add(new Option(`${state.settings.autopilot_interval} seconds`, state.settings.autopilot_interval));
  }
  $("#autopilot-interval").value = state.settings.autopilot_interval;
  $("#autopilot-screenshots").checked = state.settings.autopilot_screenshots;
  $("#autopilot-cooldown").value = state.settings.autopilot_cooldown_seconds;
  $("#autopilot-schedule").value = state.settings.autopilot_schedule;
  selectAppearance(state.settings.theme);
  openDialog("settings-dialog");
}

function selectAppearance(theme) {
  $("#theme-select").value = theme;
  $$("[data-theme-choice]").forEach(button => {
    button.classList.toggle("active", button.dataset.themeChoice === theme);
    button.setAttribute("aria-pressed", String(button.dataset.themeChoice === theme));
  });
}

function confirmDelete(title, copy, callback) {
  $("#confirm-title").textContent = title;
  $("#confirm-copy").textContent = copy;
  $("#confirm-accept").onclick = async () => {
    $("#confirm-dialog").close();
    await callback();
  };
  $("#confirm-cancel").onclick = () => $("#confirm-dialog").close();
  openDialog("confirm-dialog");
  $("#confirm-cancel").focus();
}

async function send() {
  if (state?.busy) { toast("Let this thought finish, or press Stop before sending another."); return; }
  if (state?.voice?.active) { toast("Stop recording to review your message before sending."); return; }
  if (!state?.settings.connection_ready) { openSettings(); return; }
  const text = $("#prompt").value.trim();
  if (!text && !state?.attachment && state?.voice?.draft_seconds == null) { $("#prompt").focus(); return; }
  switchView("chat");
  autoScroll = true;
  const result = await call("send", { text });
  if (result && !result.cancelled) {
    $("#prompt").value = "";
    resizePrompt();
    $("#live-status").textContent = "Your companion is responding.";
  }
}

function resizePrompt() {
  const input = $("#prompt");
  input.style.height = "auto";
  input.style.height = `${Math.min(160, Math.max(66, input.scrollHeight))}px`;
}

const commands = [
  ["Collapse to the companion orb", "circle", "dock", "Alt X"],
  ["Hide all Cutex windows", "eye-off", "hide-companion", "Alt Shift H"],
  ["Talk through the companion orb", "messages-square", "quick-reply", "Alt Shift Q"],
  ["Start / stop a voice message", "mic", "record", "Alt Shift V"],
  ["Pause / resume Autopilot", "eye", "toggle-autopilot", "Alt Shift P"],
  ["Back to conversation", "messages-square", "view-chat", ""],
  ["New conversation", "plus", "new", "Ctrl N"],
  ["Open compact overlay / workspace", "panels-top-left", "overlay", "Alt Shift O"],
  ["Share primary screen", "monitor", "capture-screen", ""],
  ["Share a region", "scan", "capture-region", "Alt Shift S"],
  ["Open your memories", "notebook-pen", "view-memories", ""],
  ["Save a memory from this chat", "sparkles", "summarize", ""],
  ["Add a memory", "bookmark", "add-memory", ""],
  ["Customize your companion", "orbit", "view-companion", ""],
  ["Find a conversation", "search", "search", ""],
  ["Import a conversation or memory", "folder-input", "import", ""],
  ["Export this conversation", "download", "export", ""],
  ["Keep window on top", "pin", "pin", ""],
  ["Stop the response", "square", "stop", "Esc"],
  ["Preferences and shortcuts", "settings-2", "settings", ""],
];

function renderCommands() {
  const query = $("#command-search").value.toLowerCase();
  const filtered = commands.filter(command => command[0].toLowerCase().includes(query));
  const sessions = (state?.sessions || []).filter(session => session.messages.length && (!query || session.title.toLowerCase().includes(query)
    || session.messages.some(message => message.text.toLowerCase().includes(query)))).slice(0, 12);
  commandIndex = Math.max(0, Math.min(commandIndex, filtered.length + sessions.length - 1));
  $("#command-list").innerHTML = filtered.map((command, index) => `<button class="command-item ${index === commandIndex ? "selected" : ""}" data-command="${command[2]}">${icon(command[1])}<span>${command[0]}</span><kbd>${command[3]}</kbd></button>`).join("")
    + (sessions.length ? '<div class="popover-caption">YOUR CONVERSATIONS</div>' + sessions.map((session, index) => `<button class="command-item ${index + filtered.length === commandIndex ? "selected" : ""}" data-palette-session="${escapeHTML(session.id)}">${icon("message-square")}<span>${escapeHTML(session.title)}</span></button>`).join("") : "")
    || '<p class="session-empty">No matching actions or conversations. Try another word.</p>';
  icons($("#command-list"));
}

async function action(name, button) {
  switch (name) {
    case "new": {
      const result = await call("new_session");
      if (result) { state = result; switchView("chat"); $("#prompt").focus(); }
      break;
    }
    case "load-earlier": {
      const scroll = $("#conversation-scroll");
      const previousHeight = scroll.scrollHeight;
      const previousTop = scroll.scrollTop;
      autoScroll = false;
      visibleMessageLimit += 80;
      renderMessages();
      scroll.scrollTop = previousTop + scroll.scrollHeight - previousHeight;
      break;
    }
    case "settings": openSettings(); break;
    case "hide-companion": await call("hide_companion"); break;
    case "record": {
      if (recordingActionPending) break;
      recordingActionPending = true; renderVoice();
      try { await call("record"); }
      finally { recordingActionPending = false; renderVoice(); }
      break;
    }
    case "cancel-recording": await call("cancel_recording"); break;
    case "clear-voice": await call("clear_voice"); break;
    case "play-voice": await call("play_voice"); break;
    case "stop-audio": await call("stop_audio"); break;
    case "read-message": await call("read_message", { id: button.dataset.message }); break;
    case "test-connection": {
      button.disabled = true;
      $("#connection-status").textContent = "Checking Google connection…";
      try {
        const saved = await call("settings", connectionSettings());
        const result = saved && await call("test_connection");
        $("#connection-status").textContent = result?.message || "Could not connect. Check the details and try again.";
      } finally { button.disabled = false; }
      break;
    }
    case "reconnect": await initialize(); break;
    case "palette":
      $("#command-search").value = ""; commandIndex = 0; renderCommands(); openDialog("palette-dialog"); break;
    case "search":
      $("#search-wrap").hidden = false;
      if (window.innerWidth <= 600) { action("palette"); break; }
      $("#session-search").focus(); break;
    case "capture-menu": togglePopover("capture-menu", button); return;
    case "chat-menu": togglePopover("chat-menu", button); return;
    case "capture-screen":
    case "capture-region": {
      if (captureBusy) return;
      captureBusy = true;
      closePopovers();
      toast(name === "capture-region" ? "Drag to select a region. Press Escape to cancel." : "Taking a look at your primary screen…");
      try {
        await call("capture", { kind: name === "capture-region" ? "region" : "screen" });
        switchView("chat");
        $("#prompt").focus();
      } finally { captureBusy = false; }
      break;
    }
    case "clear-attachment": await call("clear_attachment"); break;
    case "stop": await call("stop"); $("#live-status").textContent = "Response stopped. Your conversation is saved."; break;
    case "retry": await call("retry"); break;
    case "overlay": await call("overlay"); break;
    case "pin": await call("pin"); break;
    case "minimize": await call("minimize"); break;
    case "dock": await call("dock"); break;
    case "quick-reply": await call("quick_reply"); break;
    case "toggle-autopilot": await call("toggle_autopilot"); break;
    case "collapse-memory":
      if (await call("collapse_memory")) toast("Making a diary and starting fresh. Your original chat stays in history.");
      break;
    case "export-memory": await call("export_memory"); break;
    case "clear": { const fresh = await call("clear"); if (fresh) { state = fresh; switchView("chat"); } break; }
    case "refresh": { const fresh = await call("refresh"); if (fresh) { state = fresh; render(); toast("A fresh coat of pixels."); } break; }
    case "quit": await call("quit"); break;
    case "import": {
      const result = await call("import");
      if (result?.name) { toast(`Brought in ${result.name}.`); switchView(result.kind === "memory" ? "memories" : "chat"); }
      break;
    }
    case "export": {
      const result = await call("export");
      if (result?.saved) toast("Your conversation is saved as a portable JSON file.");
      break;
    }
    case "summarize":
      if (await call("summarize")) toast("Making a memory diary. Your conversation will stay right here.");
      break;
    case "add-memory":
      $("#memory-form").reset(); openDialog("memory-dialog"); break;
    case "delete-chat":
      confirmDelete("Let this conversation go?", "This removes it from this device. Export a copy first if you’d like to keep it.", () => call("delete_session", { id: state.active_session })); break;
    case "refresh-models": {
      const button = $("#refresh-models");
      button.disabled = true;
      if (!await call("settings", connectionSettings())) { button.disabled = false; return; }
      $("#model-help").textContent = state.settings.provider === "vertex" ? "Loading the current Google model presets…" : "Checking the models available to your key…";
      const models = await call("models");
      button.disabled = false;
      if (models) {
        $("#available-models").innerHTML = models.map(model => `<option value="${escapeHTML(model.id)}">${escapeHTML(model.name)}</option>`).join("");
        $("#model-help").textContent = state.settings.provider === "vertex" ? "Current Google models. Use Save & test to verify access for your project." : `${models.length} models found. Start typing or open the list to choose.`;
      } else $("#model-help").textContent = "Could not refresh. Check your saved key and connection.";
      break;
    }
    case "view-memories": switchView("memories"); break;
    case "view-companion": switchView("companion"); break;
    case "view-chat": switchView("chat"); break;
  }
  closePopovers();
}

document.addEventListener("click", async event => {
  const target = event.target;
  const anchor = target.closest("a");
  if (anchor) {
    event.preventDefault();
    const url = anchor.getAttribute("href");
    if (/^https?:\/\//i.test(url)) await call("open_link", { url });
    return;
  }
  const linkButton = target.closest("[data-url]");
  if (linkButton) { await call("open_link", { url: linkButton.dataset.url }); return; }
  const closer = target.closest("[data-close]");
  if (closer) { $(`#${closer.dataset.close}`).close(); return; }
  const command = target.closest("[data-command]");
  if (command) { $("#palette-dialog").close(); await action(command.dataset.command, command); return; }
  const paletteSession = target.closest("[data-palette-session]");
  if (paletteSession) {
    $("#palette-dialog").close();
    const result = await call("select_session", { id: paletteSession.dataset.paletteSession });
    if (result) { state = result; switchView("chat"); }
    return;
  }
  const actionButton = target.closest("[data-action]");
  const companionButton = target.closest("[data-companion]");
  if (companionButton) {
    const result = await call("select_companion", { id: companionButton.dataset.companion });
    if (result) { state = result; fillPersona(); render(); }
    return;
  }
  const removeCompanion = target.closest("[data-delete-companion]");
  if (removeCompanion) {
    confirmDelete("Remove this companion?", "Their saved personality and avatar will be removed. Your conversations stay intact.", () => call("delete_companion", { id: removeCompanion.dataset.deleteCompanion }));
    return;
  }
  const avatarIcon = target.closest("[data-avatar-icon]");
  if (avatarIcon) {
    const { canvas, context } = avatarCanvas();
    context.fillStyle = "#263126"; context.fillRect(0, 0, 96, 96);
    context.font = '58px "Segoe UI Emoji"'; context.textAlign = "center"; context.textBaseline = "middle";
    context.fillText(avatarIcon.dataset.avatarIcon, 48, 51);
    draftAvatar = canvas.toDataURL("image/png");
    $("#persona-form").dataset.dirty = "true"; renderAvatar(); return;
  }
  if (actionButton) { await action(actionButton.dataset.action, actionButton); return; }
  const nav = target.closest("[data-view]");
  if (nav) { switchView(nav.dataset.view); return; }
  const session = target.closest("[data-session]");
  if (session) { const result = await call("select_session", { id: session.dataset.session }); if (result) { state = result; switchView("chat"); } return; }
  const mode = target.closest("[data-mode]");
  if (mode) { await call("settings", { mode: mode.dataset.mode }); return; }
  const captureMode = target.closest("[data-capture-mode]");
  if (captureMode) { await call("settings", { capture_mode: captureMode.dataset.captureMode }); closePopovers(); return; }
  const preset = target.closest("[data-preset]");
  if (preset) {
    const value = presets[Number(preset.dataset.preset)];
    $("#persona-name").value = value.name; $("#persona-instructions").value = value.persona;
    $("#persona-form").dataset.dirty = "true"; renderPresets(); return;
  }
  const theme = target.closest("[data-theme-choice]");
  if (theme) { selectAppearance(theme.dataset.themeChoice); return; }
  const copyButton = target.closest("[data-copy-message]");
  if (copyButton) {
    const message = activeSession().messages.find(message => message.id === copyButton.dataset.copyMessage);
    if (message && await call("copy", { text: message.text })) toast("Copied, ready for wherever it goes next.");
    return;
  }
  const remember = target.closest("[data-remember-message]");
  if (remember) {
    const message = activeSession().messages.find(message => message.id === remember.dataset.rememberMessage);
    $("#memory-title").value = activeSession().title;
    $("#memory-text").value = message.text;
    openDialog("memory-dialog"); return;
  }
  const deletion = target.closest("[data-delete-memory]");
  if (deletion) { confirmDelete("Let this memory go?", "It will no longer be saved or included in conversations.", () => call("delete_memory", { id: deletion.dataset.deleteMemory })); return; }
  const starter = target.closest("[data-starter]");
  if (starter) {
    if (starter.dataset.starter === "screen") { $("#prompt").value = "Help me understand what’s on my screen."; await action("capture-region", starter); }
    else { $("#prompt").value = starter.dataset.starter === "think" ? "There’s something I’d like to think through with you. " : "Hey, I could use a little company. How’s it going?"; $("#prompt").focus(); }
    resizePrompt(); return;
  }
  if (!target.closest(".popover")) closePopovers();
});

document.addEventListener("change", async event => {
  const input = event.target;
  if (input.dataset.setting) {
    const key = input.dataset.setting;
    const update = { [key]: input.checked };
    if (key === "share_context" && !input.checked && !state.settings.autopilot_screenshots) update.autopilot_enabled = false;
    const result = await call("settings", update);
    if (!result && state) input.checked = state.settings[key];
  }
  if (input.dataset.memoryToggle) await call("update_memory", { id: input.dataset.memoryToggle, enabled: input.checked });
});

$("#composer").addEventListener("submit", event => { event.preventDefault(); send(); });
$("#prompt").addEventListener("input", resizePrompt);
let lastTypingActivity = 0;
$("#prompt").addEventListener("input", () => {
  if (Date.now() - lastTypingActivity > 2000) { lastTypingActivity = Date.now(); call("activity", {}, true); }
});
$("#prompt").addEventListener("keydown", event => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) { event.preventDefault(); send(); }
});
$("#session-search").addEventListener("input", () => { if (state) renderSessions(); });
$("#conversation-scroll").addEventListener("scroll", () => {
  autoScroll = nearBottom();
  $("#jump-latest").hidden = autoScroll || !activeSession()?.messages.length;
});
$("#jump-latest").addEventListener("click", () => { autoScroll = true; scrollBottom(true); });
$("#persona-form").addEventListener("input", () => { $("#persona-form").dataset.dirty = "true"; });
$("#new-companion").addEventListener("click", () => {
  editingCompanionId = null; draftAvatar = "";
  $("#persona-name").value = ""; $("#persona-instructions").value = "";
  $("#persona-form").dataset.dirty = "true";
  renderAvatar(); renderPresets(); $("#persona-name").focus();
});
$("#reset-avatar").addEventListener("click", () => {
  draftAvatar = ""; $("#persona-form").dataset.dirty = "true"; renderAvatar();
});
$("#avatar-file").addEventListener("change", async event => {
  const file = event.target.files[0];
  if (!file) return;
  $("#persona-form").dataset.dirty = "true";
  try {
    if (!["image/png", "image/jpeg", "image/webp"].includes(file.type) || file.size > 5 * 1024 * 1024) throw new Error("Choose a PNG, JPEG, or WebP image under 5 MB.");
    const image = await createImageBitmap(file);
    const { canvas, context } = avatarCanvas();
    const size = Math.min(image.width, image.height);
    context.drawImage(image, (image.width-size)/2, (image.height-size)/2, size, size, 0, 0, 96, 96);
    image.close(); draftAvatar = canvas.toDataURL("image/png"); renderAvatar();
  } catch (error) { toast(error.message || "That image could not be opened. Try another one."); }
  event.target.value = "";
});
$("#original-personas").addEventListener("change", event => {
  const name = event.target.value;
  if (!originalPersonas?.[name]) return;
  $("#persona-name").value = name;
  $("#persona-instructions").value = originalPersonas[name];
  $("#persona-form").dataset.dirty = "true";
  renderPresets();
});
$("#persona-form").addEventListener("submit", async event => {
  event.preventDefault();
  const result = await call("save_companion", { id: editingCompanionId, name: $("#persona-name").value.trim(), persona: $("#persona-instructions").value.trim(), avatar: draftAvatar });
  if (result) { state = result; fillPersona(); render(); toast("Companion saved. Right here with you."); }
});
$("#memory-form").addEventListener("submit", async event => {
  event.preventDefault();
  if (await call("add_memory", { title: $("#memory-title").value.trim(), text: $("#memory-text").value.trim() })) {
    $("#memory-dialog").close(); toast("A little detail, remembered.");
  }
});
$("#key-form").addEventListener("submit", async event => {
  event.preventDefault();
  const key = $("#api-key").value.trim();
  if (!key) { toast("Paste a new key to update it. Your saved key stays in place."); return; }
  if (await call("save_key", { key })) {
    $("#api-key").value = "";
    $("#key-status").textContent = "Connected · key protected by Windows";
    toast("Your key is protected and ready. You can refresh the model list now.");
  }
});
$("#settings-form").addEventListener("submit", async event => {
  event.preventDefault();
  const result = await call("settings", {
    ...connectionSettings(), theme: $("#theme-select").value,
    voice_replies: $("#voice-replies").checked,
    opacity: Number($("#opacity-input").value) / 100,
    autopilot_interval: Number($("#autopilot-interval").value),
    autopilot_screenshots: $("#autopilot-screenshots").checked,
    autopilot_cooldown_seconds: Number($("#autopilot-cooldown").value),
    autopilot_schedule: $("#autopilot-schedule").value.trim(),
  });
  if (result) { $("#settings-dialog").close(); toast("A little more your own. Preferences saved."); }
});
function connectionSettings() {
  return { model: $("#model-input").value.trim(), provider: $("#provider-input").value,
    vertex_project: $("#vertex-project").value.trim(), vertex_location: $("#vertex-location").value.trim(),
    vertex_account: $("#vertex-account").value.trim() };
}
$("#provider-input").addEventListener("change", event => {
  $("#cloud-fields").hidden = event.target.value !== "vertex";
  $("#key-form").hidden = event.target.value === "vertex";
});
$("#opacity-input").addEventListener("input", event => { $("#opacity-value").textContent = `${event.target.value}%`; });
$("#command-search").addEventListener("input", () => { commandIndex = 0; renderCommands(); });
$("#command-search").addEventListener("keydown", event => {
  const buttons = $$(".command-item");
  if (["ArrowDown", "ArrowUp"].includes(event.key)) {
    event.preventDefault();
    if (!buttons.length) return;
    commandIndex = (commandIndex + (event.key === "ArrowDown" ? 1 : -1) + buttons.length) % buttons.length;
    renderCommands();
    $(".command-item.selected")?.scrollIntoView({ block: "nearest" });
  } else if (event.key === "Enter") { event.preventDefault(); $(".command-item.selected")?.click(); }
});
document.addEventListener("keydown", event => {
  if (event.ctrlKey && event.key.toLowerCase() === "k") { event.preventDefault(); action("palette"); }
  if (event.ctrlKey && event.key.toLowerCase() === "n" && !$("dialog[open]")) { event.preventDefault(); action("new"); }
  if (event.key === "Escape" && !$("dialog[open]")) { closePopovers(); if (state?.busy) call("stop"); }
});
window.addEventListener("resize", closePopovers);
window.addEventListener("contextmenu", event => { if (!event.target.closest("textarea,input,.message-content")) event.preventDefault(); });

window.cutex = {
  receive(event) {
    if (event.type === "state") {
      const wasBusy = state?.busy;
      state = event.state;
      render();
      if (wasBusy && !state.busy) $("#live-status").textContent = "Response finished. Your conversation is saved.";
    } else if (event.type === "chunk") {
      const session = state?.sessions.find(session => session.id === event.session_id);
      const message = session?.messages.find(message => message.id === event.message_id);
      if (!message) return;
      message.text += event.text;
      if (session.id !== state.active_session) return;
      const node = $(`[data-message-id="${CSS.escape(message.id)}"]`);
      if (node) {
        node.classList.add("streaming");
        $(".message-content", node).innerHTML = markdown(message.text);
        scrollBottom();
      }
    } else if (event.type === "voice") { if (state) { state.voice = event.voice; renderVoice(); } }
    else if (event.type === "toast") toast(event.text, event.error);
    else if (event.type === "focus") { switchView("chat"); $("#prompt").focus(); }
  },
};

async function initialize() {
  const initial = await Promise.race([
    call("state", {}, true),
    new Promise(resolve => setTimeout(() => resolve(null), 8000)),
  ]);
  if (!initial || initial === true) {
    $("#connection-banner").hidden = false;
    $("#connection-banner").innerHTML = `${icon("plug-zap")}<span>The desktop connection didn’t finish. Reopen Cutex or try again.</span><button data-action="reconnect">Try again ↗</button>`;
    icons($("#connection-banner"));
    $("#live-status").textContent = "The desktop connection is unavailable.";
    return;
  }
  $("#connection-banner").innerHTML = connectionBannerHTML;
  icons($("#connection-banner"));
  state = initial;
  render();
  $("#live-status").textContent = "Your workspace is ready.";
}
window.addEventListener("pywebviewready", initialize);
const hour = new Date().getHours();
$("#greeting").textContent = hour < 12 ? "A LITTLE SPACE FOR YOUR MORNING" : hour < 18 ? "MAKE A LITTLE ROOM FOR YOURSELF" : "GOOD EVENING. MAKE YOURSELF AT HOME.";
icons();
if (window.pywebview?.api) initialize();
