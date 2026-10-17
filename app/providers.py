"""Model calls. Gemini perceives photos/voice, tutor answers go through a fallback chain."""
import io
import subprocess
import json
import logging
import os
import re
import wave

import httpx

log = logging.getLogger("ajarlok")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
GEMINI_TTS_MODEL = os.getenv("GEMINI_TTS_MODEL", "gemini-3.8-flash-tts")
TUTOR_ORDER = [p.strip() for p in os.getenv("TUTOR_ORDER", "ilmu,qwen,gemini").split(",") if p.strip()]
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "1500"))

_gemini = None


def gemini():
    global _gemini
    if _gemini is None:
        from google import genai
        _gemini = genai.Client()  # reads GEMINI_API_KEY, or GOOGLE_GENAI_USE_VERTEXAI + GOOGLE_CLOUD_PROJECT
    return _gemini


def gemini_configured() -> bool:
    return bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_GENAI_USE_VERTEXAI"))


GEMINI_AUDIO = {"audio/mp3", "audio/mpeg", "audio/wav", "audio/x-wav", "audio/aiff", "audio/aac", "audio/ogg", "audio/flac"}


def to_mp3(data: bytes) -> bytes:
    """Browsers record webm/mp4 opus, which Gemini does not list as supported. Convert to small mono MP3."""
    import imageio_ffmpeg

    out = subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-i", "pipe:0",
         "-vn", "-ac", "1", "-ar", "16000", "-b:a", "32k", "-f", "mp3", "pipe:1"],
        input=data, capture_output=True, timeout=30, check=True,
    )
    return out.stdout


def perceive(note: str, image: tuple[bytes, str] | None, audio: tuple[bytes, str] | None) -> dict:
    """Turn a photo and/or voice note into question text + language using Gemini."""
    from google.genai import types
    from .prompts import PERCEIVE_PROMPT

    if audio and audio[1] not in GEMINI_AUDIO:
        audio = (to_mp3(audio[0]), "audio/mp3")
    kind = " and ".join(k for k, v in (("photo", image), ("voice recording", audio)) if v)
    parts = [types.Part.from_bytes(data=m[0], mime_type=m[1]) for m in (image, audio) if m]
    parts.append(PERCEIVE_PROMPT.format(kind=kind, note=note or "(none)"))
    resp = gemini().models.generate_content(
        model=GEMINI_MODEL,
        contents=parts,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    data = json.loads(resp.text)
    return {"question": data.get("question") or note, "language": data.get("language", "")}


def _clean_turns(system: str, history: list[dict], question: str) -> list[dict]:
    """OpenAI-style messages that start with user and alternate roles."""
    turns = []
    for t in history + [{"role": "user", "content": question}]:
        role = "assistant" if t.get("role") == "assistant" else "user"
        text = str(t.get("content", "")).strip()
        if not text:
            continue
        if turns and turns[-1]["role"] == role:
            turns[-1]["content"] += "\n\n" + text
        else:
            turns.append({"role": role, "content": text})
    while turns and turns[0]["role"] != "user":
        turns.pop(0)
    return turns


def _openai_compat(prefix: str, system: str, turns: list[dict]) -> str:
    base, key, model = (os.getenv(f"{prefix}_{k}") for k in ("BASE_URL", "API_KEY", "MODEL"))
    if not (base and key and model):
        raise RuntimeError(f"{prefix} not configured")
    r = httpx.post(
        base.rstrip("/") + "/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": model, "messages": [{"role": "system", "content": system}] + turns, "max_tokens": MAX_TOKENS},
        timeout=45,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _qwen(system: str, turns: list[dict]) -> str:
    """Qwen 27B via SovernStack (custom API, reply text is in "message")."""
    url, user, model = (os.getenv(k) for k in ("QWEN_URL", "QWEN_USER_ID", "QWEN_MODEL"))
    if not (url and user and model):
        raise RuntimeError("qwen not configured")
    r = httpx.post(
        url,
        headers={"x-user-id": user, "x-model": model},
        json={"messages": [{"role": "system", "content": system}] + turns, "temperature": 0.7, "max_tokens": MAX_TOKENS},
        timeout=45,
    )
    r.raise_for_status()
    return r.json()["message"]


def _gemini_tutor(system: str, turns: list[dict]) -> str:
    if not gemini_configured():
        raise RuntimeError("gemini not configured")
    from google.genai import types

    contents = [{"role": "model" if t["role"] == "assistant" else "user", "parts": [{"text": t["content"]}]} for t in turns]
    resp = gemini().models.generate_content(
        model=GEMINI_MODEL, contents=contents,
        config=types.GenerateContentConfig(system_instruction=system, max_output_tokens=MAX_TOKENS),
    )
    return resp.text


PROVIDERS = {
    "ilmu": lambda s, t: _openai_compat("ILMU", s, t),
    "qwen": _qwen,
    "gemini": _gemini_tutor,
}


def tutor(system: str, history: list[dict], question: str) -> tuple[str, str]:
    """Try each provider in TUTOR_ORDER, return (answer, provider_name)."""
    turns = _clean_turns(system, history, question)
    errors = []
    for name in TUTOR_ORDER:
        fn = PROVIDERS.get(name)
        if not fn:
            continue
        try:
            text = fn(system, turns)
            text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()
            if text:
                return text, name
        except Exception as e:  # fall through to the next provider
            log.warning("tutor provider %s failed: %s", name, e)
            errors.append(f"{name}: {e}")
    raise RuntimeError("All tutor providers failed. " + " | ".join(errors))


def tts(text: str) -> bytes:
    """Gemini TTS, returns a WAV file (24 kHz 16-bit mono PCM)."""
    from google.genai import types

    resp = gemini().models.generate_content(
        model=GEMINI_TTS_MODEL,
        contents=text,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore"))
            ),
        ),
    )
    pcm = resp.candidates[0].content.parts[0].inline_data.data
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(pcm)
    return buf.getvalue()
