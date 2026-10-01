/**
 * AudioWorkletProcessor -- MicCapture16kHz
 * Runs on the audio rendering thread (no GC pauses, no jitter).
 * Native sample rate -> linear downsample to 16 kHz -> Int16 little-endian PCM.
 * Posts 80 ms frames to main thread via postMessage.
 *
 * Post message schema:
 *   { type: "pcm_chunk", buffer: Int16Array.buffer }
 *   { type: "vad_rms", rms: number }
 */

class MicCapture16kHz extends AudioWorkletProcessor {
    constructor() {
        super();
        this._targetRate = 16000;
        this._nativeRate = sampleRate; // global in AudioWorklet scope
        this._ratio = this._nativeRate / this._targetRate;

        // 80 ms at 16 kHz = 1280 samples
        this._frameSizeSamples = Math.floor(this._targetRate * 0.08);
        this._outBuffer = new Float32Array(this._frameSizeSamples);
        this._outPtr = 0;
        this._resampAcc = 0;
        this._active = false;
        this._vadCounter = 0;

        // Ring buffer for last ~1040 ms (13 frames of 80ms)
        this._preBufferFrames = [];
        this._maxPreBufferFrames = 13;

        this.port.onmessage = (e) => {
            if (e.data.type === "set_active") {
                const wasActive = this._active;
                this._active = !!e.data.value;
                if (this._active && !wasActive) {
                    // Flush pre-buffer first so start of speech is never lost
                    while (this._preBufferFrames.length > 0) {
                        const item = this._preBufferFrames.shift();
                        this.port.postMessage({
                            type: "pcm_chunk",
                            buffer: item.buffer,
                            rms: item.rms,
                            is_speech: item.is_speech,
                            is_prebuffer: true
                        }, [item.buffer]);
                    }
                    this.port.postMessage({ type: "active_confirmed" });
                } else if (!this._active) {
                    this._preBufferFrames = [];
                }
            }
        };
    }

    process(inputs) {
        const input = inputs[0];
        if (!input || !input[0]) return true; // Always keep processor alive!
        const raw = input[0];

        // RMS energy for VAD visualiser
        let sumSq = 0;
        for (let i = 0; i < raw.length; i++) sumSq += raw[i] * raw[i];
        const rms = Math.sqrt(sumSq / raw.length);
        this._vadCounter++;
        if (this._vadCounter >= 10) {
            this.port.postMessage({ type: "vad_rms", rms });
            this._vadCounter = 0;
        }

        // Linear resample and accumulate into 80 ms frames
        let srcIdx = this._resampAcc;
        while (srcIdx < raw.length) {
            const intIdx = Math.floor(srcIdx);
            const frac = srcIdx - intIdx;
            const s0 = raw[intIdx];
            const s1 = (intIdx + 1 < raw.length) ? raw[intIdx + 1] : s0;
            this._outBuffer[this._outPtr++] = s0 + frac * (s1 - s0);

            if (this._outPtr >= this._frameSizeSamples) {
                let sumSqFrame = 0;
                for (let i = 0; i < this._frameSizeSamples; i++) {
                    sumSqFrame += this._outBuffer[i] * this._outBuffer[i];
                }
                const chunkRms = Math.sqrt(sumSqFrame / this._frameSizeSamples);
                const isSpeech = chunkRms >= 0.008;

                const int16 = new Int16Array(this._frameSizeSamples);
                for (let i = 0; i < this._frameSizeSamples; i++) {
                    const c = Math.max(-1, Math.min(1, this._outBuffer[i]));
                    int16[i] = c < 0 ? Math.round(c * 32768) : Math.round(c * 32767);
                }

                if (this._active) {
                    this.port.postMessage({
                        type: "pcm_chunk",
                        buffer: int16.buffer,
                        rms: chunkRms,
                        is_speech: isSpeech
                    }, [int16.buffer]);
                } else {
                    // Mic is inactive: preserve trailing ~1000 ms in ring buffer
                    this._preBufferFrames.push({
                        buffer: int16.buffer,
                        rms: chunkRms,
                        is_speech: isSpeech
                    });
                    if (this._preBufferFrames.length > this._maxPreBufferFrames) {
                        this._preBufferFrames.shift();
                    }
                }
                this._outPtr = 0;
            }
            srcIdx += this._ratio;
        }

        this._resampAcc = Math.max(0, srcIdx - raw.length);
        return true;
    }
}

registerProcessor("mic-capture-16khz", MicCapture16kHz);
