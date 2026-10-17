import json
import logging
import re
import time
from collections import defaultdict, deque
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse, Response  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from . import providers  # noqa: E402
from .prompts import ACTIONS, tutor_system  # noqa: E402

logging.basicConfig(level=logging.INFO)
STATIC = Path(__file__).parent / "static"
MAX_UPLOAD = 4 * 1024 * 1024

app = FastAPI(title="AjarLok")

# Same patterns as scrub() in the page, for clients that skip the browser.
PII = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[EMEL]"),
    (re.compile(r"\b(?:\d[ -]?){15,18}\d\b"), "[KAD]"),
    (re.compile(r"\b\d{6}[- ]?\d{2}[- ]?\d{4}\b"), "[IC]"),
    (re.compile(r"(?:\+?60|\b0)1\d[- ]?\d{3,4}[- ]?\d{4}\b"), "[TELEFON]"),
    (re.compile(r"(?:\+?60|\b0)[3-9]\d?[- ]?\d{3,4}[- ]?\d{3,4}\b"), "[TELEFON]"),
]


def scrub(s: str) -> str:
    for pattern, tag in PII:
        s = pattern.sub(tag, s)
    return s


# Simple per-IP limit so a script can't run up the model bill. In-memory is fine for one small instance.
RATE_LIMIT, RATE_WINDOW = 30, 60
_hits: dict[str, deque] = defaultdict(deque)


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    if request.url.path.startswith("/api/") and request.url.path != "/api/ping":
        ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "")).split(",")[0].strip()
        now, hits = time.time(), _hits[ip]
        while hits and hits[0] < now - RATE_WINDOW:
            hits.popleft()
        if len(hits) >= RATE_LIMIT:
            return JSONResponse({"detail": "Terlalu banyak soalan. Tunggu sekejap. / Too many requests, please wait a minute."}, 429)
        hits.append(now)
    return await call_next(request)


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
        hist = [{**t, "content": scrub(str(t.get("content", "")))} for t in json.loads(history)[-8:] if isinstance(t, dict)]
    except json.JSONDecodeError:
        hist = []

    question, language = scrub(text.strip()), ""
    if img or aud:
        try:
            p = providers.perceive(question, img, aud)
            question, language = scrub(p["question"]), p["language"]
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
