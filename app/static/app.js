// Meeting Shadow Agent — browser client.
// Audio path: (Meet tab | sample file) -> AudioWorklet (PCM16 @16k) -> wss://streaming.assemblyai.com/v3/ws (token auth)
// Text path:  finalized Turn (end_of_turn=true) -> POST /api/suggest -> suggestion card with evidence ids.
// Nothing is auto-sent or auto-spoken. The engineer chooses to adopt / hold / copy.

const WS_BASE = "wss://streaming.assemblyai.com/v3/ws";
const $ = (id) => document.getElementById(id);
const state = { ws: null, ctx: null, stream: null, turns: [], seq: 0, t0: 0, busy: false, lastSuggestedId: null };

function log(msg, cls = "") {
  const el = document.createElement("div");
  el.className = "log " + cls;
  el.textContent = `${((performance.now() - state.t0) / 1000).toFixed(1)}s ${msg}`;
  $("log").prepend(el);
}

async function getToken() {
  const r = await fetch("/api/token", { method: "POST" });
  if (!r.ok) throw new Error(`token ${r.status}: ${await r.text()}`);
  return r.json();
}

function connect(token) {
  // Verified against /docs/api-reference/streaming-api/universal-3-pro-streaming (2026-09-07):
  // on universal-3-5-pro, `mode` is the primary turn-detection knob; `format_turns` and
  // `end_of_turn_confidence_threshold` are ignored (turn_is_formatted always tracks end_of_turn).
  const q = new URLSearchParams({
    token,
    speech_model: "universal-3-5-pro",
    encoding: "pcm_s16le",
    sample_rate: "16000",
    mode: "balanced", // week-1 latency gate decides whether min_latency is needed
    language_codes: "en",
    prompt: "English technical meeting between software engineers about delivery dates, environments (staging vs production), scope and approvals.",
  });
  const ws = new WebSocket(`${WS_BASE}?${q}`);
  ws.binaryType = "arraybuffer";
  ws.onopen = () => log("ws open", "ok");
  ws.onclose = (e) => log(`ws close ${e.code}`);
  ws.onerror = () => log("ws error", "err");
  ws.onmessage = (ev) => onMessage(JSON.parse(ev.data));
  return ws;
}

function onMessage(m) {
  if (m.type === "Begin") { log(`session ${m.id}`); return; }
  if (m.type === "Termination") { log(`terminated audio=${m.audio_duration_seconds}s`); return; }
  if (m.type !== "Turn") return;
  $("partial").textContent = m.transcript;
  if (m.end_of_turn) { // on U3.5 Pro a final turn is already formatted
    const id = `u${++state.seq}`;
    const t = { id, text: m.transcript, t_ms: Math.round(performance.now() - state.t0) };
    state.turns.push(t);
    const li = document.createElement("li");
    li.id = id;
    li.innerHTML = `<b>[${id}]</b> ${t.text}`;
    $("turns").prepend(li);
    $("partial").textContent = "";
    requestSuggestion();
  }
}

async function requestSuggestion() {
  if (state.busy) return; // ponytail: drop overlapping requests; latest turn triggers the next one.
  state.busy = true;
  const started = performance.now();
  const body = { premise: $("premise").value.slice(0, 1000), utterances: state.turns.slice(-8) };
  try {
    const r = await fetch("/api/suggest", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
    const ms = Math.round(performance.now() - started);
    if (!r.ok) { log(`suggest ${r.status}: ${await r.text()}`, "err"); return; }
    renderSuggestion(await r.json(), ms);
  } finally { state.busy = false; }
}

function renderSuggestion(s, ms) {
  $("latency").textContent = `${ms} ms (turn end → card)`;
  $("summary").textContent = s.summary_ja;
  $("unconfirmed").innerHTML = s.unconfirmed.map((u) => `<li>${esc(u.item)} <span class="ev">${u.evidence_ids.join(" ")}</span></li>`).join("") || "<li class=\"muted\">未確定事項なし</li>";
  $("nextEn").textContent = s.next_line_en;
  $("nextJa").textContent = s.next_line_ja;
  $("evidence").textContent = s.evidence_ids.join(" ");
  $("card").classList.toggle("danger", s.commits_to_something);
  $("commitWarn").hidden = !s.commits_to_something;
  for (const li of $("turns").children) li.classList.toggle("cited", s.evidence_ids.includes(li.id));
  log(`card ${ms} ms`, ms <= 3000 ? "ok" : "warn");
}

function esc(x) { return x.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c])); }

async function startWithStream(stream, ctx) {
  state.t0 = performance.now();
  state.turns = []; state.seq = 0; $("turns").innerHTML = "";
  const tok = await getToken();
  $("cap").textContent = `demo sessions left today: ${tok.sessions_left_today}`;
  state.ws = connect(tok.token);
  await new Promise((res, rej) => { state.ws.addEventListener("open", res, { once: true }); state.ws.addEventListener("error", rej, { once: true }); });
  state.ctx = ctx || new AudioContext();
  await state.ctx.audioWorklet.addModule("/static/pcm-worklet.js");
  const src = state.ctx.createMediaStreamSource(stream);
  const node = new AudioWorkletNode(state.ctx, "pcm-worklet");
  node.port.onmessage = (e) => { if (state.ws && state.ws.readyState === 1) state.ws.send(e.data); };
  src.connect(node); // not connected to destination: we listen, we do not play back.
  state.stream = stream;
  stream.getAudioTracks()[0].onended = stop;
  setTimeout(stop, tok.max_session_duration_seconds * 1000); // hard client-side stop; server token also expires.
  $("stop").disabled = false;
}

async function startMeetTab() {
  // Chrome: user must pick a *tab* and tick "Share tab audio". Video is required by the API but never leaves the browser.
  const stream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: true });
  if (stream.getAudioTracks().length === 0) {
    stream.getTracks().forEach((t) => t.stop());
    alert("音声トラックがありません。タブを選び「タブの音声を共有」をオンにしてください。");
    return;
  }
  stream.getVideoTracks().forEach((t) => t.stop()); // drop video immediately
  await startWithStream(stream);
}

async function startSample() {
  // Sample audio is pre-recorded; recognition and suggestion run live. No transcript or answer key is preloaded.
  // Order matters: token + WebSocket + worklet must be wired before playback starts, otherwise the first ~0.5 s
  // is lost ("Thanks for joining." was heard as "training." in the first browser run).
  const audio = new Audio("/static/samples/sample-01.wav");
  audio.preload = "auto";
  state.ctx = new AudioContext();
  const dest = state.ctx.createMediaStreamDestination();
  state.ctx.createMediaElementSource(audio).connect(dest);
  await startWithStream(dest.stream, state.ctx);
  await audio.play();
}

function stop() {
  if (state.ws && state.ws.readyState === 1) state.ws.send(JSON.stringify({ type: "Terminate" }));
  state.stream?.getTracks().forEach((t) => t.stop());
  state.ctx?.close();
  $("stop").disabled = true;
}

window.addEventListener("beforeunload", stop); // an abandoned session bills until the 3 h cap: always Terminate
$("meet").onclick = () => startMeetTab().catch((e) => log(e.message, "err"));
$("sample").onclick = () => startSample().catch((e) => log(e.message, "err"));
$("stop").onclick = stop;
$("copy").onclick = () => navigator.clipboard.writeText($("nextEn").textContent);
$("adopt").onclick = () => { state.lastSuggestedId = state.turns.at(-1)?.id; log("adopted (not sent anywhere)"); };
$("hold").onclick = () => log("held");
