import json
import os
import asyncio
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect, status
from fastapi.responses import FileResponse
from google import genai
from google.genai import types

BASE_DIR = Path(__file__).resolve().parent.parent
RESUME_DIR = BASE_DIR / "Resume"
TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "index.html"
PARSED_RESUME_PATH = RESUME_DIR / "parsed_resume.json"
LIVE_MODEL = "gemini-live-2.5-flash-preview"
load_dotenv(BASE_DIR / ".env")

app = FastAPI()

EXTRACTION_PROMPT = """
Extract only the useful technical interview information from this resume.
Return JSON with exactly these keys:
{
  "name": "candidate full name or empty string",
    "experience": ["short summaries of relevant work or practical experience"],
  "skills": ["technical skills only"],
  "tools_and_technologies": ["programming languages, frameworks, libraries, databases, cloud platforms, and tools"],
  "projects": [
    {
      "name": "project name",
      "description": "one short sentence",
      "technologies": ["technologies used"]
    }
  ]
}

Ignore college, school, grades, marks, address, phone number, email, links,
certifications, and other personal details. Do not invent information. Use an
empty string or empty array when a value is not present.
"""

INTERVIEW_INSTRUCTION = """
You are a friendly technical interviewer. Conduct a structured live interview
using the candidate resume JSON below. Ask one question at a time, wait for a
complete answer, and ask a short follow-up when useful. Keep the interview
focused on technical ability and the candidate's practical experience.

Follow this order:
1. Introduction: welcome the candidate and ask for a brief 60-90 second
    introduction. Mention that they should focus on their relevant experience,
    technical knowledge, and strongest skills. Do not ask technical questions
    before this introduction is complete.
2. Fundamentals: ask a few questions about the foundations behind the
    candidate's listed skills.
3. Skills and tools: ask targeted questions based on the candidate's skills,
    tools, and technologies. Adjust difficulty based on their answers.
4. Projects and experience: choose the most relevant project or experience
    from the resume and ask about the candidate's contribution, decisions,
    challenges, and technical tradeoffs.
5. Closing: ask whether the candidate wants to add anything relevant, then
    briefly end the interview.

Do not ask about college, school, grades, contact details, or other personal
information. Do not invent resume details. Start only with the introduction
request.

Candidate resume JSON:
"""


@app.get("/")
def main_page() -> FileResponse:
    return FileResponse(TEMPLATE_PATH)


@app.get("/home")
def resume_upload() -> FileResponse:
    return FileResponse(TEMPLATE_PATH)


@app.post("/upload_resume")
async def upload_pdf(pdf_file: UploadFile = File(...)) -> dict:
    if pdf_file.content_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Only PDF files are allowed.",
        )

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GEMINI_API_KEY is not configured.",
        )

    resume_bytes = await pdf_file.read()
    RESUME_DIR.mkdir(exist_ok=True)

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(data=resume_bytes, mime_type="application/pdf"),
                EXTRACTION_PROMPT,
            ],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        parsed_resume = json.loads(response.text)
        PARSED_RESUME_PATH.write_text(
            json.dumps(parsed_resume, indent=2),
            encoding="utf-8",
        )
    except json.JSONDecodeError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Gemini returned invalid JSON.",
        ) from error
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Resume parsing failed: {error}",
        ) from error
    finally:
        await pdf_file.close()

    return {
        "status": "success",
        "message": "Resume parsed successfully.",
        "resume": parsed_resume,
    }


@app.websocket("/ws/interview")
async def interview_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        await websocket.send_json({"type": "error", "message": "GEMINI_API_KEY is not configured."})
        await websocket.close(code=1011)
        return

    if not PARSED_RESUME_PATH.exists():
        await websocket.send_json({"type": "error", "message": "Upload and parse a resume first."})
        await websocket.close(code=1008)
        return

    resume = json.loads(PARSED_RESUME_PATH.read_text(encoding="utf-8"))
    client = genai.Client(api_key=api_key)
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=INTERVIEW_INSTRUCTION + json.dumps(resume),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )

    async def send_model_messages(session) -> None:
        async for message in session.receive():
            server_content = message.server_content
            if not server_content:
                continue

            if server_content.model_turn:
                for part in server_content.model_turn.parts:
                    if part.inline_data and part.inline_data.data:
                        await websocket.send_bytes(part.inline_data.data)
                    if part.text:
                        await websocket.send_json({"type": "model_text", "text": part.text})

            if server_content.output_transcription and server_content.output_transcription.text:
                await websocket.send_json(
                    {
                        "type": "model_transcript",
                        "text": server_content.output_transcription.text,
                    }
                )

            if server_content.input_transcription and server_content.input_transcription.text:
                await websocket.send_json(
                    {
                        "type": "candidate_transcript",
                        "text": server_content.input_transcription.text,
                    }
                )

    try:
        async with client.aio.live.connect(model=LIVE_MODEL, config=config) as session:
            await websocket.send_json({"type": "connected"})
            await session.send_client_content(
                turns=types.Content(
                    role="user",
                    parts=[types.Part(text="Start the interview now.")],
                )
            )
            model_task = asyncio.create_task(send_model_messages(session))

            try:
                while True:
                    incoming = await websocket.receive()
                    if incoming.get("bytes") is not None:
                        await session.send_realtime_input(
                            audio=types.Blob(
                                data=incoming["bytes"],
                                mime_type="audio/pcm;rate=16000",
                            )
                        )
                    elif incoming.get("text") is not None:
                        message = json.loads(incoming["text"])
                        if message.get("type") == "text" and message.get("text"):
                            await session.send_client_content(
                                turns=types.Content(
                                    role="user",
                                    parts=[types.Part(text=message["text"])],
                                )
                            )
            finally:
                model_task.cancel()
                await asyncio.gather(model_task, return_exceptions=True)
    except WebSocketDisconnect:
        pass
    except Exception as error:
        try:
            await websocket.send_json({"type": "error", "message": f"Interview connection failed: {error}"})
            await websocket.close(code=1011)
        except RuntimeError:
            pass