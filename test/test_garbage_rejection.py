import asyncio
import json
import time
import websockets

async def test_garbage_transcript_rejection():
    uri = "ws://127.0.0.1:8000/ws/interview"
    print(f"[TEST-REJECT] Connecting to {uri}...")
    
    async with websockets.connect(uri) as ws:
        init_payload = {
            "candidate_name": "Garbage Test Candidate",
            "level": "L5",
            "tier": "SENIOR"
        }
        await ws.send(json.dumps(init_payload))
        
        # Await greeting
        greeting_done = False
        start_time = time.time()
        while not greeting_done and (time.time() - start_time) < 25:
            msg = await ws.recv()
            if isinstance(msg, str):
                data = json.loads(msg)
                if data.get("event") == "turn_complete":
                    greeting_done = True

        print("[TEST-REJECT] Alex greeting done. Sending mic_start and 3.2s audio...")
        await ws.send(json.dumps({"event": "mic_start"}))
        await asyncio.sleep(0.1)

        # Stream 3.2 seconds of audio (40 chunks of 80ms)
        sample_rate = 16000
        samples_per_chunk = int(sample_rate * 0.08)
        for chunk_idx in range(40):
            pcm = bytearray(samples_per_chunk * 2)  # silence/muffle
            await ws.send(bytes(pcm))
            await asyncio.sleep(0.01)

        print("[TEST-REJECT] Streamed 3.2s of audio (102,400 bytes). Now sending garbage/short transcript (<15 chars)...")
        await ws.send(json.dumps({
            "event": "end_of_speech",
            "transcript": "uh huh yes"  # 10 chars < 15 chars on >3s audio
        }))

        # Await Alex's clarification response
        print("[TEST-REJECT] Awaiting clarification response...")
        received_candidate_tx = False
        received_alex_clarification = False
        clarification_text = ""
        wait_start = time.time()

        while not received_alex_clarification and (time.time() - wait_start) < 25:
            msg = await ws.recv()
            if isinstance(msg, str):
                data = json.loads(msg)
                event = data.get("event")
                if event == "candidate_transcript":
                    received_candidate_tx = True
                    print(f"[TEST-REJECT] Server emitted candidate_transcript: '{data.get('text')}'")
                elif event == "ai_transcript_chunk":
                    clarification_text += data.get("text", "")
                elif event == "turn_complete":
                    received_alex_clarification = True
                    print(f"\n[TEST-REJECT] Clarification complete: '{clarification_text}'")

        assert received_alex_clarification, "Did not receive clarification response"
        print(f"[TEST-REJECT] Clarification text: '{clarification_text}'")
        assert "catch" in clarification_text.lower() or "repeat" in clarification_text.lower() or "clearly" in clarification_text.lower() or "again" in clarification_text.lower(), f"Unexpected response: {clarification_text}"
        print("[TEST-REJECT] Rejection guard verified successfully!")

if __name__ == "__main__":
    asyncio.run(test_garbage_transcript_rejection())
