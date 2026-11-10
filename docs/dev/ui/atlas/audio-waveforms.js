/* openQ4 atlas playback graphs. Authored source; no bundled voice recordings.
   Decode a user-selected file once and read its PCM peaks at the audio element's
   playback cursor. Drawing never advances the clock or opens a microphone. */
A.audioSources = new Map();
A.playbackPeaks = (source, count, ago = 0) => {
  const result = new Float32Array(count), stream = A.audioSources.get(source);
  if (!stream || !stream.peaks || stream.media.ended || stream.media.currentTime <= 0) return result;
  const cursor = stream.media.currentTime + ago;
  for (let i = 0; i < count; i++) {
    const index = Math.floor(cursor * 60) - (count - 1 - i);
    if (index >= 0 && index < stream.peaks.length) result[i] = stream.peaks[index];
  }
  return result;
};
A.voiceLevel = now => A.playbackPeaks("radio", 1, Math.min(0, (now - performance.now()) / 1000))[0];
const stockWaveform = A.waveform;
A.waveform = (parent, options) => {
  if (options.mode !== "voice") return stockWaveform(parent, options);
  const { rect: [x, y, w, h], clip, color = "#FF8000", source = "radio", still = false } = options;
  const cid = id("audio"), count = 40;
  const mask = svgEl("path", { d: clip }, svgEl("clipPath", { id: cid }, parent));
  const bounds = mask.getBBox();
  const plotX = bounds.width > 0 ? bounds.x : x, plotW = bounds.width > 0 ? bounds.width : w;
  const g = svgEl("g", { "clip-path": `url(#${cid})`, "data-audio-source": source }, parent);
  const ink = svgEl("g", { style: "mix-blend-mode:screen;mix-blend-mode:plus-lighter" }, g);
  const bars = Array.from({length: count}, (_, i) => svgEl("rect", {
    x: plotX + i * plotW / count, width: plotW / count, fill: color
  }, ink));
  const set = () => {
    const peaks = A.playbackPeaks(source, count);
    bars.forEach((bar, i) => {
      const peak = peaks[reduce ? count - 1 : i];
      const height = Math.max(1, h * .024) + h * .64 * peak * peak;
      bar.setAttribute("y", y + (h - height) / 2);
      bar.setAttribute("height", height);
    });
  };
  set();
  // Reduced motion retains the stationary level indication. No invented trace,
  // horizontal motion, phase offset or whole-graph pumping remains.
  if (!still) A.tick(g, set);
  return { g, set, level: () => A.playbackPeaks(source, 1)[0] };
};

function audioPreviewControls(anchor, source, label) {
  if (!anchor) return;
  const box = document.createElement("div");
  box.className = "hudctl audio-preview";
  box.style.cssText = "display:flex;flex-wrap:wrap;gap:10px;align-items:center;padding:12px 0";
  const caption = document.createElement("label");
  caption.textContent = label + " ";
  const input = document.createElement("input");
  input.type = "file"; input.accept = "audio/*"; input.setAttribute("aria-label", label);
  caption.append(input);
  const media = document.createElement("audio");
  media.controls = true; media.preload = "auto"; media.setAttribute("aria-label", label + " playback");
  const status = document.createElement("span");
  status.className = "cap"; status.setAttribute("role", "status");
  status.textContent = "Choose a local audio file; the graph stays flat until playback. Nothing is uploaded.";
  box.append(caption, media, status); anchor.after(box);
  const stream = { media, peaks: null, url: null, revision: 0 };
  A.audioSources.set(source, stream);
  input.addEventListener("change", async () => {
    const file = input.files[0], revision = ++stream.revision;
    media.pause(); stream.peaks = null; media.removeAttribute("src"); media.load();
    if (stream.url) URL.revokeObjectURL(stream.url);
    stream.url = null;
    if (!file) return;
    status.textContent = "Reading audio…";
    let context;
    try {
      context = new AudioContext();
      const pcm = await context.decodeAudioData(await file.arrayBuffer());
      if (revision !== stream.revision) return;
      const peaks = new Float32Array(Math.ceil(pcm.duration * 60));
      for (let c = 0; c < pcm.numberOfChannels; c++) {
        const data = pcm.getChannelData(c);
        for (let i = 0; i < data.length; i++) {
          const bin = Math.floor(i * 60 / pcm.sampleRate);
          peaks[bin] = Math.max(peaks[bin], Math.min(1, Math.abs(data[i])));
        }
      }
      stream.peaks = peaks;
      stream.url = URL.createObjectURL(file); media.src = stream.url;
      status.textContent = "Press Play. This graph follows this file, including its pauses. Seeking and pausing stay synchronized.";
    } catch (error) {
      if (revision === stream.revision) status.textContent = "This audio file could not be decoded. Choose a supported audio file.";
    } finally {
      if (context) await context.close();
    }
  });
  media.addEventListener("error", () => {
    stream.peaks = null;
    status.textContent = "Playback unavailable; the graph is flat.";
  });
}
audioPreviewControls(document.getElementById("radioAnat")?.parentElement, "radio", "Incoming transmission");
audioPreviewControls(document.getElementById("mpVoice")?.closest(".hudctl"), "voice:Kaz", "Received voice · Kaz");
audioPreviewControls(document.querySelector('[aria-label="Received voice · Kaz"]')?.closest(".audio-preview"), "voice:self", "Your transmission");
