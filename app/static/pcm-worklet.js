// AudioWorklet: downmix to mono, resample to 16 kHz, emit Int16 PCM (pcm_s16le) chunks of ~100 ms.
// Runs off the main thread. Posts ArrayBuffer transferables to the page, which forwards them to the WebSocket.
class PcmWorklet extends AudioWorkletProcessor {
  constructor() {
    super();
    this.target = 16000;
    this.ratio = sampleRate / this.target; // sampleRate is the AudioContext rate (global in worklet scope)
    this.acc = [];
    this.accLen = 0;
    this.chunk = this.target / 10; // 100 ms
    this.pos = 0;
  }
  process(inputs) {
    const input = inputs[0];
    if (!input || input.length === 0) return true;
    const ch = input.length;
    const n = input[0].length;
    const mono = new Float32Array(n);
    for (let c = 0; c < ch; c++) for (let i = 0; i < n; i++) mono[i] += input[c][i] / ch;
    // ponytail: linear-interpolation resampler. Good enough for speech; swap for a polyphase filter if transcripts degrade.
    const out = [];
    while (this.pos < n) {
      const i0 = Math.floor(this.pos);
      const i1 = Math.min(i0 + 1, n - 1);
      const f = this.pos - i0;
      out.push(mono[i0] * (1 - f) + mono[i1] * f);
      this.pos += this.ratio;
    }
    this.pos -= n;
    this.acc.push(out);
    this.accLen += out.length;
    if (this.accLen >= this.chunk) {
      const buf = new Int16Array(this.accLen);
      let k = 0;
      for (const a of this.acc) for (const v of a) buf[k++] = Math.max(-1, Math.min(1, v)) * 0x7fff;
      this.acc = [];
      this.accLen = 0;
      this.port.postMessage(buf.buffer, [buf.buffer]);
    }
    return true;
  }
}
registerProcessor("pcm-worklet", PcmWorklet);
