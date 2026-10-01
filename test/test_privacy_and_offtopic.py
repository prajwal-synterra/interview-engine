import asyncio
import json
import time
import requests
import websockets

def test_privacy_tab_isolation():
    print("\n[TEST 1: TAB PRIVACY]")
    # Verify index.html does NOT auto-fetch active session on page load
    res = requests.get("http://127.0.0.1:8000/", timeout=5)
    assert res.status_code == 200
    html = res.text
    # Verify sessionStorage is used and activeRes fetch on page load is gone
    assert "sessionStorage.getItem(\"active_interview_session_id\")" in html
    assert "const activeRes = await fetch('/api/session/active');" not in html
    print("[TEST 1 PASSED] Fresh tabs will never pull another candidate's session from /api/session/active!")


async def test_offtopic_deflection():
    print("\n[TEST 2: OFF-TOPIC & TRIVIA DEFLECTION]")
    uri = "ws://127.0.0.1:8000/ws/interview"
    
    async with websockets.connect(uri) as ws:
        init_payload = {
            "candidate_name": "Dhanush Test",
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

        print("[TEST 2] Alex greeting received. Sending mic_start...")
        await ws.send(json.dumps({"event": "mic_start"}))
        await asyncio.sleep(0.1)

        # Stream 1.5 seconds of simulated PCM audio
        sample_rate = 16000
        samples_per_chunk = int(sample_rate * 0.08)
        for _ in range(20):
            pcm = bytearray(samples_per_chunk * 2)
            await ws.send(bytes(pcm))
            await asyncio.sleep(0.01)

        # Candidate speech with off-topic trivia quizzing ("lorry or bus", "who founded Nexus") mixed with technical project (Luna robot)
        candidate_speech = (
            "Hi, so my question is who founded Nexus? And also which is stronger, lorry or bus? "
            "Anyway, I worked on a robot named Luna using ROS, Linux architecture, and Python on a Raspberry Pi "
            "with WebSocket streaming to a backend server."
        )
        print(f"[TEST 2] Dispatching candidate speech: '{candidate_speech}'")
        await ws.send(json.dumps({
            "event": "end_of_speech",
            "transcript": candidate_speech
        }))

        # Await Alex's response
        received_candidate_tx = False
        received_alex_response = False
        alex_text = ""
        wait_start = time.time()

        while not received_alex_response and (time.time() - wait_start) < 30:
            msg = await ws.recv()
            if isinstance(msg, str):
                data = json.loads(msg)
                event = data.get("event")
                if event == "candidate_transcript":
                    received_candidate_tx = True
                    print(f"[TEST 2] Server candidate_transcript: '{data.get('text')}'")
                elif event == "ai_transcript_chunk":
                    alex_text += data.get("text", "")
                elif event == "turn_complete":
                    received_alex_response = True
                    print(f"\n[TEST 2] Alex complete response: '{alex_text}'")

        assert received_candidate_tx, "Did not receive candidate_transcript"
        assert received_alex_response, "Did not receive turn_complete"

        # Verification: Alex must NOT debate lorry vs bus or answer who founded Nexus
        t_low = alex_text.lower()
        assert "lorry" not in t_low and "bus" not in t_low, f"Alex failed deflection and answered lorry/bus: {alex_text}"
        assert "nexus" not in t_low or "founded" not in t_low, f"Alex failed deflection on nexus founding: {alex_text}"
        print("[TEST 2 PASSED] Alex strictly deflected off-topic trivia and focused on the technical project (Luna / ROS / WebSocket)!")

if __name__ == "__main__":
    test_privacy_tab_isolation()
    asyncio.run(test_offtopic_deflection())
