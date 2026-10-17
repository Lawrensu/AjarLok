"""Model calls. Every step has a fallback: other Gemini models first, then ILMU (YTL AI Labs)."""
import base64
import io
import json
import subprocess
import logging
import os
import re
import wave

import httpx

log = logging.getLogger("ajarlok")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
GEMINI_TTS_MODEL = os.getenv("GEMINI_TTS_MODEL", "gemini-3.8-flash-tts")
# "High demand" errors usually hit one model at a time, so try siblings before leaving Gemini.
GEMINI_MODELS = [GEMINI_MODEL] + [m.strip() for m in os.getenv("GEMINI_FALLBACK_MODELS", "gemini-3.5-flash,gemini-3.1-flash-lite").split(",") if m.strip()]
GEMINI_TTS_MODELS = [GEMINI_TTS_MODEL] + [m.strip() for m in os.getenv("GEMINI_TTS_FALLBACK_MODELS", "gemini-3.1-flash-tts-preview").split(",") if m.strip()]
ILMU_ASR_MODEL = os.getenv("ILMU_ASR_MODEL", "ilmu-asr-v4.2")
ILMU_VISION_MODEL = os.getenv("ILMU_VISION_MODEL", "ilmu-vision-v1.3")
ILMU_TTS_MODEL = os.getenv("ILMU_TTS_MODEL", "ilmu-tts-v2.1")
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


def _gemini_generate(contents, config=None, models=None):
    """generate_content on the first Gemini model that answers."""
    if not gemini_configured():
        raise RuntimeError("gemini not configured")
    errors = []
    for model in models or GEMINI_MODELS:
        try:
            return gemini().models.generate_content(model=model, contents=contents, config=config)
        except Exception as e:
            log.warning("gemini model %s failed: %s", model, e)
            errors.append(f"{model}: {e}")
    raise RuntimeError("All Gemini models failed. " + " | ".join(errors))


def _ilmu() -> tuple[str, str]:
    base, key = os.getenv("ILMU_BASE_URL"), os.getenv("ILMU_API_KEY")
    if not (base and key):
        raise RuntimeError("ILMU not configured")
    return base.rstrip("/"), key


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


def _json_obj(text: str) -> dict:
    m = re.search(r"\{.*\}", text or "", flags=re.S)
    try:
        return json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        return {}


def perceive(note: str, image: tuple[bytes, str] | None, audio: tuple[bytes, str] | None) -> dict:
    """Turn a photo and/or voice note into question text + language. Gemini first, ILMU ASR/vision as fallback."""
    if audio and audio[1] not in GEMINI_AUDIO:
        audio = (to_mp3(audio[0]), "audio/mp3")
    try:
        return _gemini_perceive(note, image, audio)
    except Exception as e:
        log.warning("gemini perceive failed, falling back to ILMU: %s", e)
        return _ilmu_perceive(note, image, audio)


def _gemini_perceive(note, image, audio) -> dict:
    from google.genai import types
    from .prompts import PERCEIVE_PROMPT

    kind = " and ".join(k for k, v in (("photo", image), ("voice recording", audio)) if v)
    parts = [types.Part.from_bytes(data=m[0], mime_type=m[1]) for m in (image, audio) if m]
    parts.append(PERCEIVE_PROMPT.format(kind=kind, note=note or "(none)"))
    resp = _gemini_generate(parts, types.GenerateContentConfig(response_mime_type="application/json"))
    data = _json_obj(resp.text)
    return {"question": data.get("question") or note, "language": data.get("language", "")}


def _ilmu_perceive(note, image, audio) -> dict:
    """ILMU speech-to-text for voice, ILMU vision for photos."""
    from .prompts import PERCEIVE_PROMPT

    base, key = _ilmu()
    if audio:
        r = httpx.post(f"{base}/audio/transcriptions", headers={"Authorization": f"Bearer {key}"},
                       data={"model": ILMU_ASR_MODEL}, files={"file": ("voice.mp3", audio[0], audio[1])}, timeout=60)
        r.raise_for_status()
        note = " ".join(x for x in (note, r.json().get("text", "").strip()) if x)
    if not image:
        return {"question": note, "language": ""}
    url = f"data:{image[1]};base64,{base64.b64encode(image[0]).decode()}"
    r = httpx.post(f"{base}/chat/completions", headers={"Authorization": f"Bearer {key}"}, timeout=60, json={
        "model": ILMU_VISION_MODEL, "max_tokens": MAX_TOKENS,
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": url}},
            {"type": "text", "text": PERCEIVE_PROMPT.format(kind="photo", note=note or "(none)")},
        ]}],
    })
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"]
    data = _json_obj(content)
    return {"question": data.get("question") or content.strip() or note, "language": data.get("language", "")}


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


def _openai_compat(prefix: str, system: str, turns: list[dict], max_tokens: int = MAX_TOKENS) -> str:
    base, key, model = (os.getenv(f"{prefix}_{k}") for k in ("BASE_URL", "API_KEY", "MODEL"))
    if not (base and key and model):
        raise RuntimeError(f"{prefix} not configured")
    r = httpx.post(
        base.rstrip("/") + "/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": model, "messages": [{"role": "system", "content": system}] + turns, "max_tokens": max_tokens},
        timeout=60,
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
    from google.genai import types

    contents = [{"role": "model" if t["role"] == "assistant" else "user", "parts": [{"text": t["content"]}]} for t in turns]
    resp = _gemini_generate(contents, types.GenerateContentConfig(system_instruction=system, max_output_tokens=MAX_TOKENS))
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


def draw(question: str, answer: str) -> str:
    """Ask for a small step-by-step SVG diagram (a few KB instead of a raster image). Gemini first, ILMU text model as fallback."""
    from google.genai import types
    from .prompts import DRAW_PROMPT

    prompt = DRAW_PROMPT.format(question=question, answer=answer)
    try:  # low thinking: ~15 s instead of ~37 s
        text = _gemini_generate(prompt, types.GenerateContentConfig(thinking_config=types.ThinkingConfig(thinking_level="low"))).text
    except Exception as e:
        log.warning("gemini draw failed, falling back to ILMU: %s", e)
        text = _openai_compat("ILMU", "You draw clear SVG diagrams for students.", [{"role": "user", "content": prompt}], max_tokens=6000)
    m = re.search(r"<svg\b.*?</svg>", text or "", flags=re.S | re.I)
    if not m:
        raise RuntimeError("No SVG in model output")
    svg = m.group(0)
    # Defence in depth: the page also renders it via <img>, where scripts never run.
    svg = re.sub(r"<(script|foreignObject)\b.*?</\1>", "", svg, flags=re.S | re.I)
    svg = re.sub(r"\son\w+\s*=\s*(\"[^\"]*\"|'[^']*')", "", svg, flags=re.I)
    svg = re.sub(r"\s(xlink:)?href\s*=\s*(\"(?!#)[^\"]*\"|'(?!#)[^']*')", "", svg, flags=re.I)
    return svg


def tts(text: str) -> tuple[bytes, str]:
    """Returns (audio bytes, mime). Gemini TTS as WAV first, ILMU TTS (a Malaysian voice, MP3) as fallback."""
    try:
        return _gemini_tts(text), "audio/wav"
    except Exception as e:
        log.warning("gemini tts failed, falling back to ILMU: %s", e)
    base, key = _ilmu()
    r = httpx.post(f"{base}/audio/speech", headers={"Authorization": f"Bearer {key}"}, timeout=60,
                   json={"model": ILMU_TTS_MODEL, "input": text, "voice": "alloy"})
    r.raise_for_status()
    return r.content, r.headers.get("content-type", "audio/mpeg")


def _gemini_tts(text: str) -> bytes:
    """Gemini TTS, returns a WAV file (24 kHz 16-bit mono PCM)."""
    from google.genai import types

    resp = _gemini_generate(
        text,
        models=GEMINI_TTS_MODELS,
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
