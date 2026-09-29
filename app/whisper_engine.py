"""
Local Lightweight Faster-Whisper Engine with Voice Isolation & Silero VAD.
Filters out background chatter, distant room noise, and focuses strictly on candidate.
"""

import io
# pyrefly: ignore [missing-import]
from faster_whisper import WhisperModel

print("[Whisper] Loading local 'base.en' model on CPU (int8)...")
whisper_model = WhisperModel("base.en", device="cpu", compute_type="int8")
print("[Whisper] Local Whisper model ready!")


def transcribe_audio_bytes(audio_bytes: bytes) -> str:
    """
    Transcribes audio bytes strictly to English, applying:
    1. Silero Neural VAD (threshold=0.65 to reject background room voices)
    2. No-speech rejection (drops ambient hum and static)
    3. Technical interview vocabulary priming
    """
    # Discard tiny audio snippets (< 20KB is under ~0.8s)
    if not audio_bytes or len(audio_bytes) < 20000:
        return ""

    try:
        audio_stream = io.BytesIO(audio_bytes)
        segments, info = whisper_model.transcribe(
            audio_stream,
            beam_size=3,
            language="en",
            condition_on_previous_text=False,
            # Silero Neural VAD: threshold 0.65 rejects quiet background voices
            vad_filter=True,
            vad_parameters=dict(
                threshold=0.65,
                min_speech_duration_ms=400,
                min_silence_duration_ms=500,
            ),
            no_speech_threshold=0.55,
            initial_prompt="Candidate Prajwal is speaking in an English technical interview about software engineering, computer science, and AI.",
        )

        text = " ".join([segment.text for segment in segments]).strip()

        # Discard empty, single-syllable, or single-word noise artifacts
        if not text or len(text.split()) < 2:
            return ""

        return text
    except Exception as e:
        print(f"[Whisper Error]: {e}")
        return ""
