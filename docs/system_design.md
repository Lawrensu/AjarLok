# System Design for AjarLok

This document describes the architecture and behaviour of AjarLok, a low bandwidth multimodal STEM tutor for rural Sarawak students.


## Goals and constraints

- Users
	- Rural and non native English speaking students
	- Cheap phones, weak signal, prepaid data
	- Low tech literacy
- Goals
	- Accept photo, voice and text questions
	- Answer in the student's language at the student's level with local examples
	- Spend as few bytes as possible per answer
- Constraints
	- Built and deployed in 90 minutes
	- No accounts and no database, history and level live in the browser only
	- One page under 50 KB with no frontend framework


## Repository structure

- `app/main.py` routes
- `app/providers.py` model calls and fallback
- `app/prompts.py` tutor prompt
- `app/static/index.html` UI with inline CSS and JS
- `requirements.txt`, `Dockerfile` (installs ffmpeg), `.env.example`


## Deployment

- Single Cloud Run service in asia southeast1 (Singapore, closest to Sarawak)
- FastAPI serves both the page and the API
- The Docker image includes ffmpeg for voice conversion


## Pipeline

1. Input Gate (browser, deterministic, before upload)
	- Picks a mode
		- `navigator.connection` saveData and effectiveType where available
		- `/api/ping` round trip as fallback since iOS lacks `navigator.connection`
		- Jimat Data toggle forces Lite
	- Compresses photos with canvas
	- Records voice with MediaRecorder at a low opus bitrate
		- webm on Android Chrome
		- mp4 on iPhone
	- Detects level from chat text or tap chips
2. Perceive (Gemini 3.8 Flash)
	- Runs only when a photo or voice note is attached
	- Turns the image or audio into clean question text and a detected language
	- Voice notes are first converted on the server to low bitrate mono MP3 with ffmpeg
		- Gemini supports MP3 but not webm
	- Text only questions skip this step to save time
3. Tutor (ILMU)
	- Answers in the student's language, including code switching
	- Pitched to the level and the KSSR or KSSM syllabus
	- Uses Sarawak examples such as padi, longhouses, the Rajang River, the Bakun dam, kek lapis and pepper farms
	- Answer length shaped by mode
4. Output Shaper and speech
	- Lite and Standard read aloud with the phone's own voice through speechSynthesis at zero data cost
	- Full uses Gemini 3.8 Flash TTS
	- Data meter shows KB uploaded plus downloaded for every answer


## Bandwidth tiers

- Lite (slow 2G, 2G, saveData or Jimat Data on)
	- Photos 512px JPEG quality 0.5
	- Voice 12 kbps
	- Answers about 120 words
	- On device speech
- Standard (3G)
	- Photos 768px JPEG quality 0.6
	- Voice 16 kbps
	- Answers about 220 words
	- On device speech
- Full (4G or WiFi)
	- Photos 1024px JPEG quality 0.7
	- Voice 24 kbps
	- Answers about 350 words
	- Gemini 3.8 Flash TTS


## Level adaptation

- Detected from chat text with simple patterns
	- umur, tahun, years old
	- darjah N, tingkatan N, form N
	- universiti
- Or chosen from tap chips
	- Darjah 1 to 3
	- Darjah 4 to 6
	- Tingkatan 1 to 3
	- Tingkatan 4 to 5
	- Universiti
- Stored in the browser and sent with every request


## Language handling

- The tutor replies in the language the student used, including mixed Bahasa Melayu and English
- Button labels follow the device language
	- Malay devices show Malay first with English underneath
	- Other devices show English first with Malay underneath
	- Every button keeps its icon
- Bahasa Melayu, English and Mandarin are well supported
- Sarawak Malay is best effort today


## User interface

- One screen
- Three big buttons with icons Ambil Gambar (Snap), Cakap (Talk) and Taip (Type)
	- Label order follows the device language, see Language handling
- One tap follow ups Lebih Mudah (Simpler), Contoh Tempatan (Local example) and Kuiz Saya (Quiz me)
- Play button on each answer
- Inspired by NotebookLM, a photo of the student's own textbook page becomes the lesson source and Kuiz Saya generates questions from it


## Model routing

- Perceive uses Gemini 3.8 Flash
	- Natively multimodal, reads image or audio and text in one call
- Tutor uses ILMU through an OpenAI compatible API
	- Malaysian LLM by YTL AI Labs, tuned for Malaysian languages
- Tutor fallback order ILMU, then Qwen, then Gemini
	- Qwen 27B is served by SovernStack through its own custom API, not OpenAI compatible
	- Qwen is a strong multilingual backup
	- Gemini is the last resort
	- Order is configurable with `TUTOR_ORDER`, default `ilmu,qwen,gemini`
	- Providers without keys are skipped


## API

- `GET /` serves the page
- `GET /api/ping` latency probe
- `POST /api/ask` multipart form
	- Fields `text`, optional `image` file, optional `audio` file, `level`, `mode` (lite, standard, full), `action` (simpler, local, quiz), `history` JSON of the last turns
	- Returns JSON with `answer`, `provider`, `level`, `language`, `question`
- `POST /api/tts` returns WAV audio from Gemini 3.8 Flash TTS, used only in Full mode


## Environment variables

- Gemini
	- `GEMINI_API_KEY`
	- `GEMINI_MODEL`
	- `GEMINI_TTS_MODEL`
- ILMU
	- `ILMU_BASE_URL`
	- `ILMU_API_KEY`
	- `ILMU_MODEL`
- Qwen
	- `QWEN_URL`
	- `QWEN_USER_ID`
	- `QWEN_MODEL`
- Routing
	- `TUTOR_ORDER`


## Deploy

```bash
gcloud run deploy ajarlok \
  --source . \
  --region asia-southeast1 \
  --allow-unauthenticated \
  --set-env-vars GEMINI_API_KEY=...,ILMU_BASE_URL=...,ILMU_API_KEY=...,ILMU_MODEL=...,QWEN_URL=...,QWEN_USER_ID=...,QWEN_MODEL=...
```


## Risks

- Gemini supports MP3 but not webm, so voice notes depend on the ffmpeg conversion working in the Docker image
- A Malay speechSynthesis voice is not on every phone, so the app falls back to an English voice or Full mode
- ILMU endpoint must follow the OpenAI compatible format, Qwen must match the SovernStack API


## Roadmap

- Telegram bot reusing `/api/ask`
- Tiny SVG diagrams in Full mode
- Two voice audio recap like NotebookLM
- Offline PWA shell
- Better Sarawak Malay support
