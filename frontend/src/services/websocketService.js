/**
 * WebSocket & Audio Service for real-time live voice interview
 * Handles bidirectional WebSocket events, PCM audio playback from Alex,
 * and 16kHz microphone PCM streaming.
 */

export class InterviewWebSocket {
  constructor({ onMessage, onStatusChange, onAudioPlayState }) {
    this.ws = null;
    this.onMessage = onMessage || (() => {});
    this.onStatusChange = onStatusChange || (() => {});
    this.onAudioPlayState = onAudioPlayState || (() => {});
    this.isConnected = false;
    this.audioCtx = null;
    this.nextPlayTime = 0;
    this.mediaStream = null;
    this.audioProcessor = null;
  }

  initAudio() {
    if (!this.audioCtx) {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (AudioContextClass) {
        this.audioCtx = new AudioContextClass({ sampleRate: 24000 });
      }
    }
    if (this.audioCtx && this.audioCtx.state === "suspended") {
      this.audioCtx.resume();
    }
  }

  playPCMChunk(arrayBuffer) {
    try {
      this.initAudio();
      if (!this.audioCtx) return;

      const alignedLength = arrayBuffer.byteLength - (arrayBuffer.byteLength % 2);
      if (alignedLength === 0) return;

      const pcmData = new Int16Array(arrayBuffer, 0, alignedLength / 2);
      const floatData = new Float32Array(pcmData.length);
      for (let i = 0; i < pcmData.length; i++) {
        floatData[i] = pcmData[i] / 32768.0;
      }

      const buffer = this.audioCtx.createBuffer(1, floatData.length, 24000);
      buffer.getChannelData(0).set(floatData);

      const source = this.audioCtx.createBufferSource();
      source.buffer = buffer;
      source.connect(this.audioCtx.destination);

      const currentTime = this.audioCtx.currentTime;
      if (this.nextPlayTime < currentTime) {
        this.nextPlayTime = currentTime;
      }
      source.start(this.nextPlayTime);
      this.nextPlayTime += buffer.duration;
      this.onAudioPlayState(true);

      source.onended = () => {
        if (this.audioCtx && this.audioCtx.currentTime >= this.nextPlayTime - 0.05) {
          this.onAudioPlayState(false);
        }
      };
    } catch (e) {
      console.warn("PCM play error:", e);
    }
  }

  connect(candidateName = "Candidate", tier = "HARD") {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.port === "5173" ? "127.0.0.1:8000" : window.location.host;
    const wsUrl = `${protocol}//${host}/ws/interview`;

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        this.isConnected = true;
        this.onStatusChange({ connected: true, latency: "0.8ms" });
        // Handshake with candidate name and seniority tier
        this.sendJson({ name: candidateName, level: tier });
      };

      this.ws.onmessage = async (event) => {
        // Binary PCM voice bytes from Alex
        if (event.data instanceof Blob) {
          const arrayBuffer = await event.data.arrayBuffer();
          this.playPCMChunk(arrayBuffer);
          return;
        } else if (event.data instanceof ArrayBuffer) {
          this.playPCMChunk(event.data);
          return;
        }

        // Control JSON messages
        if (typeof event.data === "string") {
          try {
            const data = JSON.parse(event.data);
            this.onMessage(data);
          } catch {
            this.onMessage({ event: "raw_text", text: event.data });
          }
        }
      };

      this.ws.onclose = () => {
        this.isConnected = false;
        this.onStatusChange({ connected: false, latency: "—" });
      };

      this.ws.onerror = (err) => {
        console.warn("WebSocket error:", err);
        this.isConnected = false;
        this.onStatusChange({ connected: false, latency: "Error" });
      };
    } catch (e) {
      console.warn("Could not open WebSocket:", e);
      this.onStatusChange({ connected: false, latency: "Failed" });
    }
  }

  async startMicrophone() {
    try {
      this.initAudio();
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { sampleRate: 16000, channelCount: 1 }
      });
      this.mediaStream = stream;

      const micCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
      const micSource = micCtx.createMediaStreamSource(stream);
      const processor = micCtx.createScriptProcessor(2048, 1, 1);

      processor.onaudioprocess = (e) => {
        if (!this.isConnected || !this.ws || this.ws.readyState !== WebSocket.OPEN) return;
        const inputData = e.inputBuffer.getChannelData(0);
        const pcm16 = new Int16Array(inputData.length);
        for (let i = 0; i < inputData.length; i++) {
          const s = Math.max(-1, Math.min(1, inputData[i]));
          pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        this.ws.send(pcm16.buffer);
      };

      micSource.connect(processor);
      processor.connect(micCtx.destination);
      this.audioProcessor = { micCtx, micSource, processor };
      return true;
    } catch (err) {
      console.warn("Microphone access error:", err);
      return false;
    }
  }

  stopMicrophone(transcript = "") {
    if (this.audioProcessor) {
      try {
        this.audioProcessor.processor.disconnect();
        this.audioProcessor.micSource.disconnect();
        this.audioProcessor.micCtx.close();
      } catch {}
      this.audioProcessor = null;
    }
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((track) => track.stop());
      this.mediaStream = null;
    }
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.sendJson({
        event: "end_of_speech",
        transcript: transcript
      });
    }
  }

  sendJson(payload) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(payload));
    }
  }

  sendCandidateText(text) {
    this.sendJson({
      action: "candidate_text",
      transcript: text
    });
  }

  pause() {
    this.sendJson({ action: "pause_interview" });
  }

  resume() {
    this.sendJson({ action: "resume_interview" });
  }

  finish() {
    this.sendJson({ action: "finish_interview" });
  }

  disconnect() {
    this.stopMicrophone();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.isConnected = false;
    this.onStatusChange({ connected: false, latency: "—" });
  }
}
