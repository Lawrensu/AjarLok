import json
import logging
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, File, Form, HTTPException, UploadFile  # noqa: E402
from fastapi.responses import FileResponse, Response  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from . import providers  # noqa: E402
from .prompts import ACTIONS, tutor_system  # noqa: E402

logging.basicConfig(level=logging.INFO)
STATIC = Path(__file__).parent / "static"
MAX_UPLOAD = 4 * 1024 * 1024

app = FastAPI(title="AjarLok")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/ping")
def ping():
    return {"ok": True}


async def _read(f: UploadFile | None) -> tuple[bytes, str] | None:
    if not f or not f.filename:
        return None
    data = await f.read()
    if not data:
        return None
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "File too large")
    return data, (f.content_type or "application/octet-stream").split(";")[0]


@app.post("/api/ask")
async def ask(
    text: str = Form(""),
    level: str = Form(""),
    mode: str = Form("standard"),
    action: str = Form(""),
    history: str = Form("[]"),
    image: UploadFile | None = File(None),
    audio: UploadFile | None = File(None),
):
    img, aud = await _read(image), await _read(audio)
    try:
        hist = json.loads(history)[-8:]
    except json.JSONDecodeError:
        hist = []

    question, language = text.strip(), ""
    if img or aud:
        try:
            p = providers.perceive(question, img, aud)
            question, language = p["question"], p["language"]
        except Exception as e:
            logging.exception("perceive failed")
            if not question:
                raise HTTPException(502, f"Could not read the photo/voice: {e}")
    if action in ACTIONS:
        question = ACTIONS[action] + (f"\n\n{question}" if question else "")
    if not question:
        raise HTTPException(400, "Empty question")
    # Models drift into Malay unless the language rule sits right next to the question.
    if language:
        lang_rule = f"Reply in {language}."
    elif action in ACTIONS:  # button instructions are in English, so anchor on the conversation instead
        lang_rule = "Reply in the same language as your previous answer and my earlier messages, not English unless we were using English."
    else:
        lang_rule = "Reply in the same language I used in my message above."

    try:
        answer, provider = providers.tutor(tutor_system(level, mode), hist, f"{question}\n\n({lang_rule})")
    except RuntimeError as e:
        raise HTTPException(502, str(e))
    return {"answer": answer, "provider": provider, "question": question if (img or aud) else "", "language": language}


class DrawIn(BaseModel):
    question: str = ""
    answer: str


@app.post("/api/draw")
def draw(body: DrawIn):
    try:
        return {"svg": providers.draw(body.question[:2000], body.answer[:4000])}
    except Exception as e:
        logging.exception("draw failed")
        raise HTTPException(502, str(e))


class TTSIn(BaseModel):
    text: str


@app.post("/api/tts")
def tts(body: TTSIn):
    try:
        return Response(providers.tts(body.text[:2000]), media_type="audio/wav")
    except Exception as e:
        logging.exception("tts failed")
        raise HTTPException(502, str(e))
