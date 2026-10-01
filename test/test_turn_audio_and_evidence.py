import asyncio
import json
import os
import sys
import time
import websockets

async def test_live_interview_turn():
    uri = "ws://127.0.0.1:8000/ws/interview"
    print(f"[TEST] Connecting to {uri}...")
    
    async with websockets.connect(uri) as ws:
        print("[TEST] Connected. Initializing session...")
        init_payload = {
            "candidate_name": "Prajwal Test",
            "level": "L5",
            "tier": "SENIOR"
        }
        await ws.send(json.dumps(init_payload))
        
        # Wait for session initialization and Alex's greeting
        greeting_done = False
        start_time = time.time()
        print("[TEST] Awaiting session_started and initial greeting...")
        while not greeting_done and (time.time() - start_time) < 25:
            msg = await ws.recv()
            if isinstance(msg, str):
                data = json.loads(msg)
                event = data.get("event")
                if event == "session_started":
                    print(f"[TEST] Session started: id={data.get('session_id')}")
                elif event == "ai_transcript_chunk":
                    pass
                elif event == "turn_complete":
                    print(f"[TEST] Alex finished initial greeting: '{data.get('full_text')}'")
                    greeting_done = True
            elif isinstance(msg, bytes):
                pass

        assert greeting_done, "Did not receive initial greeting from Alex within timeout"

        # 1. Test VAD Calibration dispatch
        print("\n[TEST] 1. Dispatching vad_calibration...")
        await ws.send(json.dumps({
            "event": "vad_calibration",
            "floor": 0.00285,
            "threshold": 0.00712
        }))
        await asyncio.sleep(0.2)

        # 2. Test mic_start
        print("[TEST] 2. Dispatching mic_start...")
        await ws.send(json.dumps({"event": "mic_start"}))
        await asyncio.sleep(0.1)

        # 3. Stream 2 seconds of 16kHz mono PCM16 audio (simulated speech signal)
        print("[TEST] 3. Streaming simulated 16kHz PCM audio frames...")
        # 16000 samples/sec * 2 bytes/sample * 0.08 sec = 2560 bytes per 80ms chunk
        sample_rate = 16000
        chunk_sec = 0.08
        samples_per_chunk = int(sample_rate * chunk_sec)
        total_chunks = 25  # 25 * 0.08 = 2.0 seconds
        
        for chunk_idx in range(total_chunks):
            pcm_bytes = bytearray()
            for s in range(samples_per_chunk):
                t = (chunk_idx * samples_per_chunk + s) / sample_rate
                import math
                val = 0.3 * math.sin(2 * math.pi * 220 * t) + 0.15 * math.sin(2 * math.pi * 440 * t)
                val_int16 = int(max(-32768, min(32767, val * 32767)))
                pcm_bytes.extend(val_int16.to_bytes(2, byteorder="little", signed=True))
            await ws.send(bytes(pcm_bytes))
            await asyncio.sleep(0.02)

        print(f"[TEST] Streamed {total_chunks} chunks ({total_chunks * 2560} bytes).")

        # 4. Dispatch end_of_speech with realistic Indian-accented English technical answer
        candidate_speech_text = (
            "Hi Alex, I have five years of experience building distributed backend systems. "
            "I primarily design event-driven architectures using Kafka, PostgreSQL for ACID compliance, "
            "and Redis for caching. Recently I worked on an inference orchestration service optimizing latency."
        )
        print(f"[TEST] 4. Dispatching end_of_speech ({len(candidate_speech_text)} chars)...")
        await ws.send(json.dumps({
            "event": "end_of_speech",
            "transcript": candidate_speech_text
        }))

        # 5. Receive candidate_transcript and Alex's Socratic response
        print("[TEST] 5. Awaiting candidate_transcript and Alex's response...")
        received_candidate_tx = False
        received_alex_response = False
        wait_start = time.time()

        while not received_alex_response and (time.time() - wait_start) < 30:
            msg = await ws.recv()
            if isinstance(msg, str):
                data = json.loads(msg)
                event = data.get("event")
                if event == "candidate_transcript":
                    received_candidate_tx = True
                    print(f"\n[TEST] Server emitted candidate_transcript: '{data.get('text')}'")
                elif event == "ai_transcript_chunk":
                    sys.stdout.write(data.get("text", ""))
                    sys.stdout.flush()
                elif event == "turn_complete":
                    received_alex_response = True
                    print(f"\n[TEST] Alex response complete: '{data.get('full_text')}'")

        assert received_candidate_tx, "Did not receive candidate_transcript event"
        assert received_alex_response, "Did not receive turn_complete event"
        print("\n[TEST] Turn completed successfully!")

if __name__ == "__main__":
    asyncio.run(test_live_interview_turn())
