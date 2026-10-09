/**
 * WebSocket & Audio Service for real-time live voice interview
 * Handles bidirectional WebSocket events, PCM audio playback from Alex,
 * 16kHz microphone PCM streaming, and real-time speech recognition captioning.
 */

function downsampleTo16k(input, fromRate) {
  if (fromRate === 16000) return input;
  const ratio = fromRate / 16000;
  const newLength = Math.round(input.length / ratio);
  const result = new Float32Array(newLength);
  let offsetResult = 0;
  let offsetBuffer = 0;
  while (offsetResult < result.length) {
    const nextOffsetBuffer = Math.round((offsetResult + 1) * ratio);
    let accum = 0;
    let count = 0;
    for (let i = offsetBuffer; i < nextOffsetBuffer && i < input.length; i++) {
      accum += input[i];
      count++;
    }
    result[offsetResult] = count > 0 ? accum / count : 0;
    offsetResult++;
    offsetBuffer = nextOffsetBuffer;
  }
  return result;
}

export class InterviewWebSocket {
  constructor({
    onMessage,
    onStatusChange,
    onAudioPlayState,
    onCandidateSpeechChunk,
    onCandidateSpeechFinal
  }) {
    this.ws = null;
    this.onMessage = onMessage || (() => {});
    this.onStatusChange = onStatusChange || (() => {});
    this.onAudioPlayState = onAudioPlayState || (() => {});
    this.onCandidateSpeechChunk = onCandidateSpeechChunk || (() => {});
    this.onCandidateSpeechFinal = onCandidateSpeechFinal || (() => {});
    this.isConnected = false;
    this.audioCtx = null;
    this.nextPlayTime = 0;
    this.mediaStream = null;
    this.audioProcessor = null;
    this.activeSources = [];
    this.speechRecognition = null;
    this.micChunksSent = 0;

    // Silence detection & conversational state
    this.currentCandidateTranscript = "";
    this.silenceTimer = null;
    this.silenceThresholdMs = 1500; // 1.5 seconds of silence -> auto-submit speech turn
    this.isAlexSpeaking = false;
  }

  handleSpeechActivity(text) {
    if (!text || !text.trim()) return;
    this.currentCandidateTranscript = text.trim();

    // Stream live text to UI for real-time visual feedback
    this.onCandidateSpeechChunk(this.currentCandidateTranscript, false);

    // Reset silence countdown timer
    if (this.silenceTimer) {
      clearTimeout(this.silenceTimer);
    }

    // When candidate stops talking for 1.5 seconds, auto-submit the turn!
    this.silenceTimer = setTimeout(() => {
      this.autoSubmitCandidateTurn();
    }, this.silenceThresholdMs);
  }

  autoSubmitCandidateTurn() {
    if (this.silenceTimer) {
      clearTimeout(this.silenceTimer);
      this.silenceTimer = null;
    }

    const transcriptToSubmit = (this.currentCandidateTranscript || "").trim();
    if (!transcriptToSubmit || transcriptToSubmit.length < 3) {
      return;
    }

    console.log("[SilenceDetector] Auto-submitting candidate speech turn:", transcriptToSubmit);

    // 1. Seal candidate bubble in UI
    this.onCandidateSpeechFinal(transcriptToSubmit);

    // 2. Clear current candidate transcript buffer for the next turn
    this.currentCandidateTranscript = "";

    // 3. Send over WebSocket to live_server.py so Alex immediately replies
    this.sendJson({
      action: "candidate_speech_finished",
      transcript: transcriptToSubmit
    });

    // 4. Recycle speech recognition instance so next turn accumulates cleanly
    if (this.speechRecognition) {
      try {
        this.speechRecognition.stop();
      } catch {}
    }
  }

  async initAudio() {
    if (!this.audioCtx) {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (AudioContextClass) {
        this.audioCtx = new AudioContextClass({ sampleRate: 24000 });
      }
    }
    if (this.audioCtx && this.audioCtx.state === "suspended") {
      try {
        await this.audioCtx.resume();
      } catch (e) {
        console.warn("Could not resume audioCtx:", e);
      }
    }
  }

  stopAudioPlayback() {
    if (this.activeSources && this.activeSources.length > 0) {
      this.activeSources.forEach((src) => {
        try {
          src.stop();
          src.disconnect();
        } catch {}
      });
      this.activeSources = [];
    }
    if (this.audioCtx) {
      this.nextPlayTime = this.audioCtx.currentTime;
    }
    this.isAlexSpeaking = false;
    this.onAudioPlayState(false);
  }

  async playPCMChunk(arrayBuffer) {
    try {
      await this.initAudio();
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
      this.activeSources.push(source);
      this.isAlexSpeaking = true;
      this.onAudioPlayState(true);

      source.onended = () => {
        this.activeSources = this.activeSources.filter((s) => s !== source);
        if (this.audioCtx && this.audioCtx.currentTime >= this.nextPlayTime - 0.05) {
          this.isAlexSpeaking = false;
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
            if (data.event === "ai_interrupted") {
              this.stopAudioPlayback();
            }
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
      await this.initAudio();
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });
      this.mediaStream = stream;

      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      const micCtx = new AudioContextClass();
      if (micCtx.state === "suspended") {
        await micCtx.resume();
      }

      const micSource = micCtx.createMediaStreamSource(stream);
      // 4096 samples provides responsive frames with minimal CPU jitter
      const processor = micCtx.createScriptProcessor(4096, 1, 1);
      this.micChunksSent = 0;

      processor.onaudioprocess = (e) => {
        if (!this.isConnected || !this.ws || this.ws.readyState !== WebSocket.OPEN) return;
        const inputData = e.inputBuffer.getChannelData(0);

        // Calculate audio RMS energy for candidate speech activity & barge-in
        let sumSquares = 0;
        for (let i = 0; i < inputData.length; i++) {
          sumSquares += inputData[i] * inputData[i];
        }
        const rms = Math.sqrt(sumSquares / inputData.length);

        // Barge-in: If candidate starts speaking over Alex
        if (rms > 0.035 && this.isAlexSpeaking) {
          console.log("[BargeIn] Candidate interrupted Alex (RMS:", rms.toFixed(4), ")");
          this.stopAudioPlayback();
          this.sendJson({ event: "candidate_interrupted" });
        }

        // Correctly downsample to 16kHz for Gemini Live multimodal voice input
        const downsampled = downsampleTo16k(inputData, micCtx.sampleRate);
        const pcm16 = new Int16Array(downsampled.length);
        for (let i = 0; i < downsampled.length; i++) {
          const s = Math.max(-1, Math.min(1, downsampled[i]));
          pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        this.ws.send(pcm16.buffer);
        this.micChunksSent++;
      };

      micSource.connect(processor);
      // Route through a zero-gain node so processor fires continuously without audio feedback
      const muteGain = micCtx.createGain();
      muteGain.gain.value = 0;
      processor.connect(muteGain);
      muteGain.connect(micCtx.destination);

      this.audioProcessor = { micCtx, micSource, processor, muteGain };

      // Start Web Speech API in browser for instant real-time live chat captioning & silence detection
      const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (SpeechRec) {
        try {
          const rec = new SpeechRec();
          rec.continuous = true;
          rec.interimResults = true;
          rec.lang = "en-US";

          rec.onresult = (evt) => {
            // If Alex is speaking, candidate speaking triggers barge-in
            if (this.isAlexSpeaking) {
              this.stopAudioPlayback();
              this.sendJson({ event: "candidate_interrupted" });
            }

            let fullTurnTranscript = "";
            for (let i = 0; i < evt.results.length; ++i) {
              const res = evt.results[i];
              fullTurnTranscript += (fullTurnTranscript ? " " : "") + res[0].transcript;
            }

            if (fullTurnTranscript.trim()) {
              this.handleSpeechActivity(fullTurnTranscript.trim());
            }
          };

          rec.onerror = (err) => {
            console.warn("Web Speech error:", err);
          };

          rec.onend = () => {
            // Automatically resume continuous listening for candidate's next speech turn
            if (this.mediaStream && this.speechRecognition) {
              try {
                this.speechRecognition.start();
              } catch {
                setTimeout(() => {
                  if (this.mediaStream && this.speechRecognition) {
                    try { this.speechRecognition.start(); } catch {}
                  }
                }, 100);
              }
            }
          };

          rec.start();
          this.speechRecognition = rec;
        } catch (e) {
          console.warn("Could not start SpeechRecognition:", e);
        }
      }

      return true;
    } catch (err) {
      console.warn("Microphone access error:", err);
      return false;
    }
  }

  stopMicrophone(transcript = "") {
    if (this.speechRecognition) {
      try {
        this.speechRecognition.onend = null;
        this.speechRecognition.stop();
      } catch {}
      this.speechRecognition = null;
    }
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
    if (this.silenceTimer) {
      clearTimeout(this.silenceTimer);
      this.silenceTimer = null;
    }
    this.currentCandidateTranscript = "";
    this.stopAudioPlayback(); // Barge-in: cut off Alex's audio playback immediately
    this.sendJson({
      action: "candidate_text",
      transcript: text
    });
    if (this.speechRecognition) {
      try { this.speechRecognition.stop(); } catch {}
    }
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

