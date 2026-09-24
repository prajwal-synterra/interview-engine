"""
Server — FastAPI WebSocket Server for Real-Time Voice Interview

Integrates:
- Gemini Live (gemini-3.1-flash-live-preview) for voice generation
- Gemini audio transcription for candidate speech
- LangGraph state machine (generate_question, evaluate_answer, generate_final_report)
- Real-time event broadcasting (state, logs, transcripts, audio)
"""

import os
import json
import base64
import asyncio
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.state import InterviewState
from app.nodes import (
    generate_question,
    evaluate_answer,
    generate_final_report,
)
from app.graph import route_after_evaluation, MAX_QUESTIONS
from app.agent import GeminiVoiceAgent

app = FastAPI(title="LangGraph Voice Interview Engine")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
STATIC_DIR.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def get_root():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        return {"message": "LangGraph Voice Interview Engine is running. Static UI not yet created."}
    return FileResponse(str(index_file))


class InterviewSession:
    """Orchestrates one candidate interview session over a WebSocket."""

    def __init__(self, websocket: WebSocket):
        self.ws = websocket
        self.voice_agent = GeminiVoiceAgent()
        self.is_running = False
        self.phase = "idle"  # idle | intro | in_question | completed
        self.state: InterviewState = {
            "question": "",
            "answer": "",
            "score": 0,
            "feedback": "",
            "strengths": "",
            "weaknesses": "",
            "difficulty": "easy",
            "question_number": 0,
            "questions": [],
            "answers": [],
            "scores": [],
            "feedbacks": [],
            "final_report": "",
        }

    async def send_json(self, msg: dict):
        """Send JSON message to client safely."""
        try:
            await self.ws.send_text(json.dumps(msg))
        except Exception:
            pass

    async def log(self, category: str, message: str):
        """Send log message to client debug panel and print ASCII to console."""
        print(f"[{category.upper()}] {message}")
        await self.send_json({
            "type": "log",
            "category": category,
            "message": message,
        })

    async def broadcast_state(self):
        """Send state snapshot to client for live inspector."""
        await self.send_json({
            "type": "state",
            "state": self.state,
        })

    async def set_status(self, status: str, details: Optional[str] = None):
        """Update interview UI status badge."""
        await self.send_json({
            "type": "status",
            "status": status,
            "details": details,
        })

    async def speak_text(self, text: str):
        """Stream Gemini Live audio chunks to the browser."""
        await self.set_status("speaking")
        await self.log("live", f"Gemini Live speaking: {text[:60]}...")

        try:
            async for chunk in self.voice_agent.speak_stream(text):
                b64_audio = base64.b64encode(chunk).decode("ascii")
                await self.send_json({
                    "type": "audio",
                    "data": b64_audio,
                })
        except Exception as ex:
            await self.log("error", f"Audio synthesis failed: {ex}")

        # Let client know speaking has concluded
        await self.send_json({"type": "audio_end"})

    async def start(self):
        """Start the interview with candidate introduction."""
        self.is_running = True
        self.phase = "intro"
        await self.log("graph", "Starting LangGraph Interview Session.")
        await self.broadcast_state()

        intro_prompt = (
            "Hello and welcome to your Java technical interview! "
            "I will be your AI interviewer today. "
            "Before we begin with our technical questions, "
            "please take a moment to introduce yourself, your experience, "
            "and what you have built with Java."
        )

        await self.send_json({
            "type": "transcript",
            "role": "interviewer",
            "text": intro_prompt,
        })

        await self.speak_text(intro_prompt)
        await self.set_status("listening", "Please introduce yourself...")
        await self.log("system", "Awaiting candidate introduction.")

    async def handle_candidate_response(self, text: str):
        """Handle candidate's spoken or typed answer."""
        text = text.strip()
        if not text:
            await self.log("warning", "Empty candidate response received.")
            return

        await self.send_json({
            "type": "transcript",
            "role": "candidate",
            "text": text,
        })

        loop = asyncio.get_running_loop()

        if self.phase == "intro":
            # Introduction turn completed
            await self.log("system", f"Candidate introduced: {text[:60]}...")
            self.phase = "in_question"

            ack_text = "Thank you for the introduction! That's wonderful background. Let's dive straight into your technical questions."
            await self.send_json({
                "type": "transcript",
                "role": "interviewer",
                "text": ack_text,
            })
            await self.speak_text(ack_text)

            # Proceed to first question
            await self.next_question()

        elif self.phase == "in_question":
            # Candidate answered a technical question
            self.state["answer"] = text
            await self.log("graph", f"[Node: evaluate_answer] Evaluating answer for Round {self.state['question_number']}...")
            await self.set_status("evaluating", "Analyzing your answer with LangGraph...")

            # Run evaluate_answer in worker thread to prevent blocking
            eval_result = await loop.run_in_executor(None, evaluate_answer, self.state)
            self.state.update(eval_result)

            await self.broadcast_state()

            # Send evaluation result to UI
            await self.send_json({
                "type": "evaluation",
                "round": self.state["question_number"],
                "score": self.state["score"],
                "feedback": self.state["feedback"],
                "strengths": self.state.get("strengths", ""),
                "weaknesses": self.state.get("weaknesses", ""),
                "difficulty": self.state["difficulty"],
            })

            # Spoken feedback summary
            spoken_feedback = (
                f"Thank you. Score: {self.state['score']} out of 10. {self.state['feedback']}"
            )
            await self.send_json({
                "type": "transcript",
                "role": "interviewer",
                "text": f"Evaluation for Question {self.state['question_number']}: Score {self.state['score']}/10. {self.state['feedback']}",
            })
            await self.speak_text(spoken_feedback)

            # Route using LangGraph conditional edge
            next_step = route_after_evaluation(self.state)
            await self.log("graph", f"Conditional routing: next node -> {next_step}")

            if next_step == "final_report" or self.state["question_number"] >= MAX_QUESTIONS:
                await self.generate_report()
            else:
                await self.next_question()

    async def next_question(self):
        """Generate and ask the next question using LangGraph."""
        loop = asyncio.get_running_loop()
        next_q_num = self.state["question_number"] + 1
        diff = self.state.get("difficulty", "easy").upper()

        await self.set_status("generating", f"Generating Question {next_q_num} ({diff})...")
        await self.log("graph", f"[Node: generate_question] Generating Question {next_q_num} at difficulty {diff}...")

        q_result = await loop.run_in_executor(None, generate_question, self.state)
        self.state.update(q_result)
        await self.broadcast_state()

        q_text = self.state["question"]
        q_display = f"Question {self.state['question_number']} ({self.state['difficulty'].upper()}): {q_text}"

        await self.send_json({
            "type": "transcript",
            "role": "interviewer",
            "text": q_display,
        })
        await self.send_json({
            "type": "question",
            "number": self.state["question_number"],
            "difficulty": self.state["difficulty"],
            "question": q_text,
        })

        spoken_q = f"Question {self.state['question_number']}. {q_text}"
        await self.speak_text(spoken_q)

        await self.set_status("listening", f"Listening to answer for Question {self.state['question_number']}...")
        await self.log("system", f"Awaiting candidate answer for Question {self.state['question_number']}.")

    async def generate_report(self):
        """Generate final debrief report using LangGraph."""
        self.phase = "completed"
        loop = asyncio.get_running_loop()

        await self.set_status("evaluating", "Generating final debrief report...")
        await self.log("graph", "[Node: generate_final_report] Compiling complete interview debrief...")

        report_result = await loop.run_in_executor(None, generate_final_report, self.state)
        self.state.update(report_result)
        await self.broadcast_state()

        report_content = self.state["final_report"]
        await self.send_json({
            "type": "final_report",
            "report": report_content,
        })

        await self.send_json({
            "type": "transcript",
            "role": "interviewer",
            "text": "Interview Concluded. Here is your final performance report:\n\n" + report_content,
        })

        closing_speech = (
            "Congratulations on completing your Java technical interview! "
            "Your comprehensive evaluation report has been compiled and is displayed on your screen. "
            "Thank you for your time and excellent effort today!"
        )
        await self.speak_text(closing_speech)

        await self.set_status("completed", "Interview completed.")
        await self.log("system", "Session finished successfully.")

    async def close(self):
        """Clean up voice agent and session."""
        await self.voice_agent.close()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    session = InterviewSession(websocket)

    await session.log("system", "Client connected to WebSocket server.")
    await session.broadcast_state()
    await session.set_status("ready", "Ready to start interview.")

    try:
        while True:
            raw_data = await websocket.receive_text()
            try:
                data = json.loads(raw_data)
            except Exception:
                continue

            msg_type = data.get("type")

            if msg_type == "start_interview":
                await session.start()

            elif msg_type == "candidate_text":
                text = data.get("text", "")
                await session.handle_candidate_response(text)

            elif msg_type == "candidate_audio":
                # Audio received from client browser (16kHz PCM Base64)
                b64_pcm = data.get("data", "")
                client_transcript = data.get("transcript", "").strip()

                if client_transcript:
                    # Instant client transcription available
                    await session.handle_candidate_response(client_transcript)
                elif b64_pcm:
                    pcm_bytes = base64.b64decode(b64_pcm)
                    await session.set_status("transcribing", "Transcribing candidate audio with Gemini...")
                    await session.log("api", f"Transcribing {len(pcm_bytes)} audio bytes with Gemini...")
                    transcribed_text = await session.voice_agent.transcribe_audio(pcm_bytes)
                    if transcribed_text:
                        await session.handle_candidate_response(transcribed_text)
                    else:
                        await session.log("warning", "No speech detected in candidate audio.")
                        await session.set_status("listening", "No speech detected. Please try speaking again or type your answer.")

            elif msg_type == "reset":
                await session.close()
                session = InterviewSession(websocket)
                await session.broadcast_state()
                await session.set_status("ready", "Interview reset.")
                await session.log("system", "Session reset by user.")

    except WebSocketDisconnect:
        print("[SERVER] WebSocket disconnected.")
    except Exception as e:
        print(f"[SERVER] WebSocket exception: {e}")
    finally:
        await session.close()
