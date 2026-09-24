"""
Agent — Gemini Live Voice Interface

Connects to gemini-3.1-flash-live-preview for real-time audio generation (TTS)
and audio transcription for candidate speech input.
"""

import os
import io
import wave
import asyncio
from typing import AsyncGenerator, Optional
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

LIVE_MODEL = "gemini-3.1-flash-live-preview"
TRANSCRIPTION_MODEL = os.getenv("TRANSCRIPTION_MODEL", "gemini-2.5-flash-lite")
DEFAULT_VOICE = "Puck"


def pcm_to_wav(pcm_data: bytes, sample_rate: int = 16000, num_channels: int = 1, sampwidth: int = 2) -> bytes:
    """Converts raw PCM audio bytes to standard WAV format in memory."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(num_channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()


class GeminiVoiceAgent:
    """
    Manages Gemini Live session for real-time voice streaming and speech transcription.
    """

    def __init__(self, voice_name: str = DEFAULT_VOICE):
        self.api_keys = [
            k for k in [
                os.getenv("GOOGLE_API_KEY"),
                os.getenv("FALLBACK_GOOGLE_API_KEY"),
            ] if k and k.strip()
        ]
        if not self.api_keys:
            raise ValueError("No GOOGLE_API_KEY or FALLBACK_GOOGLE_API_KEY found.")

        self.current_key_idx = 0
        self.voice_name = voice_name
        self.client = genai.Client(api_key=self.api_keys[self.current_key_idx])
        self._session = None
        self._session_context = None
        self._lock = asyncio.Lock()

    def _rotate_key(self):
        if len(self.api_keys) > 1:
            self.current_key_idx = (self.current_key_idx + 1) % len(self.api_keys)
            new_key = self.api_keys[self.current_key_idx]
            print(f"[GeminiVoiceAgent] Rotating to alternative API key index {self.current_key_idx}...")
            self.client = genai.Client(api_key=new_key)

    async def _ensure_session(self):
        """Ensures an active Gemini Live session is connected."""
        if self._session is not None:
            return

        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=self.voice_name)
                )
            ),
            system_instruction=types.Content(
                parts=[
                    types.Part.from_text(
                        text=(
                            "You are a professional, articulate, and encouraging Java technical interviewer. "
                            "When instructed to speak a question, feedback, or remark, say it clearly, "
                            "naturally, and concisely. Keep the tone warm and professional."
                        )
                    )
                ]
            ),
        )

        for _ in range(len(self.api_keys)):
            try:
                self._session_context = self.client.aio.live.connect(model=LIVE_MODEL, config=config)
                self._session = await self._session_context.__aenter__()
                return
            except Exception as ex:
                err_str = str(ex).lower()
                if "429" in err_str or "quota" in err_str or "resource_exhausted" in err_str:
                    self._rotate_key()
                    continue
                raise ex

    async def close(self):
        """Closes the current Gemini Live session."""
        async with self._lock:
            if self._session_context is not None:
                try:
                    await self._session_context.__aexit__(None, None, None)
                except Exception:
                    pass
                self._session = None
                self._session_context = None

    async def speak_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        """
        Sends text to Gemini Live and yields 24kHz 16-bit PCM audio chunks in real-time.
        """
        async with self._lock:
            try:
                await self._ensure_session()
                # Instruct Gemini to speak the given text aloud
                await self._session.send_client_content(
                    turns=[
                        types.Content(
                            role="user",
                            parts=[types.Part.from_text(text=f"Please speak the following text clearly aloud: {text}")],
                        )
                    ],
                    turn_complete=True,
                )

                async for response in self._session.receive():
                    sc = response.server_content
                    if sc and sc.model_turn:
                        for part in sc.model_turn.parts:
                            if part.inline_data and part.inline_data.data:
                                yield part.inline_data.data
                    if sc and sc.turn_complete:
                        break

            except Exception as e:
                # In case of session drop, reset session and retry once
                print(f"[GeminiVoiceAgent] Session error during speak: {e}. Reconnecting...")
                if self._session_context is not None:
                    try:
                        await self._session_context.__aexit__(None, None, None)
                    except Exception:
                        pass
                self._session = None
                self._session_context = None

                await self._ensure_session()
                await self._session.send_client_content(
                    turns=[
                        types.Content(
                            role="user",
                            parts=[types.Part.from_text(text=f"Please speak the following text clearly aloud: {text}")],
                        )
                    ],
                    turn_complete=True,
                )
                async for response in self._session.receive():
                    sc = response.server_content
                    if sc and sc.model_turn:
                        for part in sc.model_turn.parts:
                            if part.inline_data and part.inline_data.data:
                                yield part.inline_data.data
                    if sc and sc.turn_complete:
                        break

    async def transcribe_audio(self, pcm_data: bytes, sample_rate: int = 16000) -> str:
        """
        Transcribes candidate spoken audio to text using Gemini multimodal model.
        """
        if not pcm_data or len(pcm_data) < 3200:
            # Less than 0.1s of audio is considered empty
            return ""

        wav_bytes = pcm_to_wav(pcm_data, sample_rate=sample_rate)

        # Run synchronous generate_content in asyncio executor thread
        loop = asyncio.get_running_loop()

        def _do_transcribe():
            for _ in range(len(self.api_keys)):
                try:
                    resp = self.client.models.generate_content(
                        model=TRANSCRIPTION_MODEL,
                        contents=[
                            types.Part.from_bytes(data=wav_bytes, mime_type="audio/wav"),
                            (
                                "Transcribe the candidate's spoken speech from this interview audio accurately. "
                                "If there is no speech, silence, or only background noise, reply with 'NO_SPEECH'. "
                                "Otherwise, return ONLY the exact transcribed text without quotes or commentary."
                            ),
                        ],
                    )
                    text = resp.text.strip() if resp and resp.text else ""
                    if "NO_SPEECH" in text:
                        return ""
                    return text
                except Exception as ex:
                    err_str = str(ex).lower()
                    if "429" in err_str or "quota" in err_str or "resource_exhausted" in err_str:
                        self._rotate_key()
                        continue
                    print(f"[GeminiVoiceAgent] Transcription error: {ex}")
                    return ""
            return ""

        result = await loop.run_in_executor(None, _do_transcribe)
        return result
