// Meeting Shadow Agent — browser client.
// Audio path: (Meet tab | sample file) -> AudioWorklet (PCM16 @16k) -> wss://streaming.assemblyai.com/v3/ws (token auth)
// Text path:  finalized Turn (end_of_turn=true) -> POST /api/suggest -> suggestion card with evidence ids.
// Nothing is auto-sent or auto-spoken. The engineer chooses to adopt / hold / copy.

const WS_BASE = "wss://streaming.assemblyai.com/v3/ws";
const $ = (id) => document.getElementById(id);
const state = { ws: null, ctx: null, stream: null, turns: [], seq: 0, t0: 0, busy: false, lastSuggestedId: null, pending: false, timer: null, stopTimer: null, generation: 0, audio: null };

function log(msg, cls = "") {
  const el = document.createElement("div");
  el.className = "log " + cls;
  el.textContent = `${((performance.now() - state.t0) / 1000).toFixed(1)}s ${msg}`;
  $("log").prepend(el);
  while ($("log").children.length > 100) $("log").lastElementChild.remove();
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
    mode: "min_latency", // week-1 eval: balanced 15/20 <=3s (p90 3.21 s), min_latency 18/18 (p90 2.53 s)
    language_codes: "en",
    prompt: "English technical meeting between software engineers about delivery dates, environments (staging vs production), scope and approvals.",
  });
  const ws = new WebSocket(`${WS_BASE}?${q}`);
  ws.binaryType = "arraybuffer";
  ws.onopen = () => log("ws open", "ok");
  ws.onclose = (e) => { log(`ws close ${e.code}`); if (state.ws === ws) stop(); };
  ws.onerror = () => log("ws error", "err");
  ws.onmessage = (ev) => { if (state.ws === ws) onMessage(JSON.parse(ev.data)); };
  return ws;
}

function onMessage(m) {
  if (m.type === "Begin") { log(`session ${m.id}`); return; }
  if (m.type === "Termination") { log(`terminated audio=${m.audio_duration_seconds}s`); return; }
  if (m.type !== "Turn") return;
  $("partial").textContent = m.transcript;
  if (m.end_of_turn && m.transcript.trim()) { // on U3.5 Pro a final turn is already formatted
    const id = `u${++state.seq}`;
    const t = { id, text: m.transcript, t_ms: Math.round(performance.now() - state.t0) };
    state.turns.push(t);
    const li = document.createElement("li");
    li.id = id;
    li.innerHTML = `<b>[${id}]</b> ${esc(t.text)}`;
    $("turns").prepend(li);
    $("partial").textContent = "";
    // ponytail: fillers ("Right.", "Great.") stay as evidence but do not spend a Gemini call. Questions always do.
    // Keep evidence ids immutable; merge adjacent fragments into one request, not one utterance.
    if (!/^(right|great|okay|ok|yes|yeah|thanks)[.! ]*$/i.test(t.text.trim())) {
      state.pending = true;
      clearTimeout(state.timer);
      state.timer = setTimeout(() => { state.timer = null; requestSuggestion(); }, 450);
    }
    while (state.turns.length > 40) state.turns.shift();
    while ($("turns").children.length > 40) $("turns").lastElementChild.remove();
  }
}

async function requestSuggestion() {
  if (state.busy || !state.pending) return;
  state.pending = false;
  state.busy = true;
  const generation = state.generation;
  $("status").textContent = "提案を作成中…";
  const started = state.t0 + state.turns.at(-1).t_ms;
  const body = { premise: $("premise").value.slice(0, 1000), utterances: state.turns.slice(-8) };
  try {
    const r = await fetch("/api/suggest", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body), signal: AbortSignal.timeout(15000) });
    const ms = Math.round(performance.now() - started);
    if (!r.ok) { if (generation === state.generation) log(`suggest ${r.status}`, "err"); return; }
    const result = await r.json();
    if (generation === state.generation && !state.pending) renderSuggestion(result, ms);
  } catch (e) {
    if (generation === state.generation) log("提案を取得できませんでした。次の発話で再試行します。", "err");
  } finally {
    if (generation === state.generation) {
      state.busy = false;
      $("status").textContent = "音声を受信中";
      if (state.pending && !state.timer) requestSuggestion();
    }
  }
}

function renderSuggestion(s, ms) {
  for (const id of ["adopt", "hold", "copy"]) $(id).disabled = false;
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
  state.stream = stream;
  state.ctx = ctx || new AudioContext();
  const tok = await getToken();
  $("cap").textContent = `demo sessions left today: ${tok.sessions_left_today}`;
  state.ws = connect(tok.token);
  await new Promise((res, rej) => { state.ws.addEventListener("open", res, { once: true }); state.ws.addEventListener("error", rej, { once: true }); });
  await state.ctx.audioWorklet.addModule("/static/pcm-worklet.js");
  const src = state.ctx.createMediaStreamSource(stream);
  const node = new AudioWorkletNode(state.ctx, "pcm-worklet");
  node.port.onmessage = (e) => { if (state.ws && state.ws.readyState === 1) state.ws.send(e.data); };
  src.connect(node); // not connected to destination: we listen, we do not play back.
  state.stream = stream;
  stream.getAudioTracks()[0].onended = stop;
  state.stopTimer = setTimeout(stop, tok.max_session_duration_seconds * 1000); // hard client-side stop; server token also expires.
  $("stop").disabled = false;
  $("status").textContent = "音声を受信中";
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
  state.audio = audio;
  audio.preload = "auto";
  audio.onended = () => { clearTimeout(state.stopTimer); state.stopTimer = setTimeout(stop, 2500); };
  state.ctx = new AudioContext();
  const dest = state.ctx.createMediaStreamDestination();
  state.ctx.createMediaElementSource(audio).connect(dest);
  await startWithStream(dest.stream, state.ctx);
  await audio.play();
}

function stop() {
  state.generation++;
  clearTimeout(state.timer); clearTimeout(state.stopTimer);
  state.timer = null; state.pending = false; state.busy = false;
  state.audio?.pause(); state.audio = null;
  const ws = state.ws;
  if (ws?.readyState === 1) ws.send(JSON.stringify({ type: "Terminate" }));
  if (ws) setTimeout(() => ws.close(), 1000);
  state.stream?.getTracks().forEach((t) => t.stop());
  if (state.ctx && state.ctx.state !== "closed") state.ctx.close();
  state.ctx = null; state.stream = null;
  state.ws = null;
  $("meet").disabled = false; $("sample").disabled = false;
  $("status").textContent = "停止しました";
  $("stop").disabled = true;
}

window.addEventListener("beforeunload", stop); // an abandoned session bills until the 3 h cap: always Terminate
async function start(action) {
  $("meet").disabled = true; $("sample").disabled = true;
  $("status").textContent = "接続中…";
  for (const id of ["adopt", "hold", "copy"]) $(id).disabled = true;
  $("summary").textContent = "会話を受信すると、ここに確認事項を表示します。";
  $("nextEn").textContent = "—"; $("nextJa").textContent = "";
  $("unconfirmed").innerHTML = ""; $("evidence").textContent = "";
  $("partial").textContent = ""; $("latency").textContent = "";
  $("commitWarn").hidden = true; $("card").classList.remove("danger");
  try { await action(); if (!state.stream) stop(); }
  catch (e) { stop(); log("接続できませんでした。共有設定と接続を確認してください。", "err"); }
}
$("meet").onclick = () => start(startMeetTab);
$("sample").onclick = () => start(startSample);
$("stop").onclick = stop;
$("copy").onclick = async () => {
  try { await navigator.clipboard.writeText($("nextEn").textContent); log("コピーしました", "ok"); }
  catch { log("コピーできませんでした。文章を選択してコピーしてください。", "err"); }
};
$("adopt").onclick = () => { state.lastSuggestedId = state.turns.at(-1)?.id; log("adopted (not sent anywhere)"); };
$("hold").onclick = () => log("held");
