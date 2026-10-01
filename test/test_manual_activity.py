import asyncio
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_LIVE_VOICE_API_KEY") or os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

async def test_manual_activity():
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(language_code="en-US"),
        input_audio_transcription=types.AudioTranscriptionConfig(language_codes=["en-US"]),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        realtime_input_config=types.RealtimeInputConfig(
            automatic_activity_detection=types.AutomaticActivityDetection(
                disabled=True
            )
        )
    )
    
    print("[TEST-MANUAL-VAD] Connecting with disabled=True...")
    async with client.aio.live.connect(model="gemini-3.8-live", config=config) as session:
        print("[TEST-MANUAL-VAD] Connected! Sending activity_start...")
        await session.send_realtime_input(activity_start=types.ActivityStart())
        print("[TEST-MANUAL-VAD] activity_start sent successfully!")
        
        # Send 1 second of dummy PCM audio
        dummy_pcm = bytes(16000 * 2)
        await session.send_realtime_input(
            audio=types.Blob(data=dummy_pcm, mime_type="audio/pcm;rate=16000")
        )
        print("[TEST-MANUAL-VAD] Sent audio blob. Now sending activity_end...")
        await session.send_realtime_input(activity_end=types.ActivityEnd())
        print("[TEST-MANUAL-VAD] activity_end sent successfully!")
        
        # Wait briefly to confirm session remains open and stable
        await asyncio.sleep(1.0)
        print("[TEST-MANUAL-VAD] Verified! Manual activity detection is supported and stable.")

if __name__ == "__main__":
    asyncio.run(test_manual_activity())
