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
	- Keep children's personal data off the wire
- Constraints
	- Built and deployed in 90 minutes
	- No accounts and no database, history and level live in the browser only
	- One page of about 20 KB with no frontend framework, sent gzip compressed so it downloads in about 8 KB


## Repository structure

- `app/main.py` routes, rate limit and server side redaction
- `app/providers.py` model calls, fallback, SVG diagrams and TTS
- `app/prompts.py` tutor, perceive and draw prompts
- `app/static/index.html` UI with inline CSS and JS
- `requirements.txt`, `Dockerfile`, `.env.example`


## Deployment

- Single Cloud Run service in asia southeast1 (Singapore, closest to Sarawak)
- FastAPI serves both the page and the API
- Voice conversion uses the ffmpeg binary bundled with the imageio ffmpeg Python package, so the image needs no system ffmpeg


## Pipeline

1. Input Gate (browser, deterministic, before upload)
	- Picks a mode
		- `navigator.connection` saveData and effectiveType where available
		- `/api/ping` round trip as fallback since iOS lacks `navigator.connection`
		- Jimat Data toggle forces Lite
	- Redacts personal data in the typed text, see Safety and privacy
	- Compresses photos with canvas
	- Records voice with MediaRecorder at a low opus bitrate
		- webm on Android Chrome
		- mp4 on iPhone
	- Detects level from chat text or tap chips
2. Perceive (Gemini chain, then ILMU)
	- Runs only when a photo or voice note is attached
	- Turns the image or audio into clean question text and a detected language
	- Gemini replaces personal details found in the photo or voice with [REDACTED]
	- Voice notes are first converted on the server to low bitrate mono MP3 with ffmpeg
		- Gemini supports MP3 but not webm
		- ILMU speech to text receives the same MP3
	- Text only questions skip this step to save time
	- If every Gemini model fails, ILMU speech to text handles voice and ILMU vision handles photos
3. Tutor (ILMU, then Qwen, then Gemini chain)
	- Answers in the student's language, including code switching
	- Pitched to the level and the KSSR or KSSM syllabus
	- Uses Sarawak examples such as padi, longhouses, the Rajang River, the Bakun dam, kek lapis and pepper farms
	- Teaches in three beats, key idea, steps and a one line check question, with labels written in the reply language
	- Answer length shaped by mode
	- Never says it cannot draw. When a diagram is coming it numbers its steps to match and points to the diagram below
	- Child safe, see Safety and privacy
4. Follow ups
	- Senangkan, Contoh Tempatan and Kuiz Saya call `/api/ask` again with an `action`
	- The prompt for each action is written in English, so the server adds a language rule right next to the question
		- Reply in the language of the detected input, or in the language of the previous answer and earlier messages
		- Without it, replies drift back into English
5. Draw (Gemini chain at thinking level low, then ILMU)
	- Triggered by the Lukis button, or automatically when the server finds gambar, lukis, rajah, diagram, draw or picture in the final question, so typed text, voice notes and photos all count
	- Writes one step by step SVG diagram with the real numbers and labels in the student's language
		- Usually 4 to 6 KB, so it works even in Lite mode
		- Takes about 15 seconds on Gemini and about 30 seconds on ILMU
	- The server strips scripts, foreignObject, event handler attributes and external links
	- The page shows the SVG through an img element, where scripts never run
6. Output Shaper and speech
	- Lite and Standard read aloud with the phone's own voice through speechSynthesis at zero data cost
	- Full uses Gemini TTS, with ILMU TTS returning MP3 if every Gemini TTS model fails
	- Data meter counts real network bytes for every request, including diagrams, speech and the latency probe
		- Upload is the exact request body, chat history included, plus typical request headers
		- Download is the browser's own Resource Timing count, headers included
		- The page download itself is counted once and shown on the welcome screen
	- All text responses are gzip compressed, page about 60 percent smaller and answers about 35 percent smaller


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
	- Gemini TTS, with ILMU TTS as fallback
- Measured
	- A typical Lite answer is about 600 bytes to 1.2 KB
	- A 3 second voice note at 12 kbps is about 6 KB
	- The whole page is about 18 KB


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
- Follow up replies stay in the language of the conversation, not English
- Button labels follow the device language
	- Malay devices show Malay first with English underneath
	- Other devices show English first with Malay underneath
	- Every big button keeps its icon
- Follow up button labels follow the language of the answer, so a Malay answer gets Malay buttons on any device
- Bahasa Melayu, English and Mandarin are well supported
- Sarawak Malay is best effort today


## User interface

- One screen with the chat, level chips and a text box that is always visible
- Three big buttons with icons
	- Ambil Gambar (Snap) always opens the camera
	- Muat Naik (Upload) always opens the gallery
	- Cakap (Talk) records a voice note and sends it when tapped again
	- Label order follows the device language, see Language handling
- On a laptop, images can also be pasted or dragged and dropped into the text box
- Follow ups on every answer
	- Dengar (Listen)
	- Lukis (Draw)
	- Senangkan (Simpler)
	- Contoh Tempatan (Local Example)
	- Kuiz Saya (Quiz Me)
- Answer formatting
	- HTML is escaped first, then bold and headings are rendered
	- Bullets render as dots and code formatting is removed
- A note under the buttons reminds students not to share personal information
- Inspired by NotebookLM, a photo of the student's own textbook page becomes the lesson source and Kuiz Saya generates questions from it


## Safety and privacy

- Personal data redaction
	- Runs on the phone before anything is sent, and again on the server for clients that skip the browser
	- IC numbers become [IC]
	- Malaysian mobile and landline numbers, including Sarawak 082 numbers, become [TELEFON]
	- Emails become [EMEL]
	- Card numbers become [KAD]
	- Maths numbers are untouched
	- Applies to typed text and to the history sent with each request
- Photos and voice cannot be redacted on the phone, so the Gemini perceive prompt replaces personal details with [REDACTED]
- The tutor prompt is child safe
	- Keeps everything age appropriate and refuses anything harmful, sexual or dangerous
	- Never asks for personal details and reminds students kindly not to share them
	- On bullying, abuse, self harm or feeling unsafe, responds with care, points to a trusted teacher or parent and gives Talian Kasih 15999
- Abuse limits
	- Per IP rate limit of 30 requests a minute on the API, `/api/ping` excluded, kept in memory
	- Uploads capped at 4 MB
	- Only the last 8 turns of history are sent, 4 in Lite mode
- Answers are HTML escaped before display
- Nothing is stored on a server, there is no database


## Model routing

- Every Gemini call tries models in order and the first answer wins
	- Used for perceive on photos and voice, tutor fallback and Lukis diagrams
	- Order is Gemini 3.8 Flash, then Gemini 3.5 Flash, then Gemini 3.1 Flash Lite
	- Natively multimodal, reads image or audio and text in one call
	- Gemini TTS tries Gemini 3.8 Flash TTS, then Gemini 3.1 Flash TTS Preview
- If every Gemini model fails, ILMU takes over
	- Voice uses ILMU speech to text
	- Photos use ILMU vision
	- Listen in Full mode uses ILMU text to speech, returning MP3
	- Lukis uses the ILMU text model
- Measured in testing
	- ILMU speech to text about 1.3 seconds
	- ILMU vision about 1.4 seconds
	- ILMU text to speech about 1.8 seconds
	- ILMU drawing about 30 seconds
- Tutor uses ILMU through an OpenAI compatible API
	- Malaysian LLM by YTL AI Labs, tuned for Malaysian languages
- Tutor fallback order ILMU, then Qwen, then Gemini chain
	- Qwen 27B is served by SovernStack through its own custom API, not OpenAI compatible
	- Qwen is a strong multilingual backup
	- Gemini chain is the last resort
	- Order is configurable with `TUTOR_ORDER`, default `ilmu,qwen,gemini`
	- Providers without keys are skipped


## API

- `GET /` serves the page
- `GET /api/ping` latency probe
- `POST /api/ask` multipart form
	- Fields `text`, optional `image` file, optional `audio` file, `level`, `mode` (lite, standard, full), `action` (simpler, local, quiz), `history` JSON of the last 8 turns (4 in Lite)
	- Returns JSON with `answer`, `provider`, `language` and `question` (the transcribed question, only for photo or voice input)
- `POST /api/draw` JSON with `question` and `answer`, returns JSON with `svg`
- `POST /api/tts` returns WAV audio from Gemini TTS, or MP3 from ILMU TTS when every Gemini TTS model fails, used only in Full mode
- Errors
	- 413 for files over 4 MB
	- 429 when the rate limit is hit
	- 502 when every provider fails


## Environment variables

- Gemini
	- `GEMINI_API_KEY`
	- `GEMINI_MODEL`
	- `GEMINI_FALLBACK_MODELS`
	- `GEMINI_TTS_MODEL`
	- `GEMINI_TTS_FALLBACK_MODELS`
- ILMU
	- `ILMU_BASE_URL`
	- `ILMU_API_KEY`
	- `ILMU_MODEL`
	- `ILMU_ASR_MODEL`
	- `ILMU_VISION_MODEL`
	- `ILMU_TTS_MODEL`
- Qwen
	- `QWEN_URL`
	- `QWEN_USER_ID`
	- `QWEN_MODEL`
- Routing
	- `TUTOR_ORDER`
	- `MAX_TOKENS` caps tutor output, default 1500
- Model defaults, fallback lists are comma separated

```
GEMINI_MODEL=gemini-3.8-flash
GEMINI_FALLBACK_MODELS=gemini-3.5-flash,gemini-3.1-flash-lite
GEMINI_TTS_MODEL=gemini-3.8-flash-tts
GEMINI_TTS_FALLBACK_MODELS=gemini-3.1-flash-tts-preview
ILMU_ASR_MODEL=ilmu-asr-v4.2
ILMU_VISION_MODEL=ilmu-vision-v1.3
ILMU_TTS_MODEL=ilmu-tts-v2.1
```


## Deploy

```bash
gcloud run deploy ajarlok \
  --source . \
  --region asia-southeast1 \
  --allow-unauthenticated \
  --set-env-vars GEMINI_API_KEY=...,ILMU_BASE_URL=...,ILMU_API_KEY=...,ILMU_MODEL=...,QWEN_URL=...,QWEN_USER_ID=...,QWEN_MODEL=...
```


## Risks

- Inputs are processed by third party model providers (Google, YTL AI Labs ILMU, SovernStack)
	- Redaction lowers the risk but is pattern based and cannot catch every detail, such as a name in a photo
	- ILMU speech to text only transcribes voice, so the perceive prompt does not redact personal details in a voice note on that path
- Gemini free tier allows only 20 requests a day per model and returns high demand errors, which is why the fallback chain exists
	- A paid Gemini key removes the daily cap
	- A paid Gemini key keeps inputs out of Google product improvement
- Gemini supports MP3 but not webm, so voice notes depend on the ffmpeg conversion working
- A Malay speechSynthesis voice is not on every phone, so the app falls back to an English voice or Full mode
- ILMU endpoints must follow the OpenAI compatible format for speech to text, vision and speech, and Qwen must match the SovernStack API
- Diagrams come from a model and can contain mistakes, the student can ask for another
- The in memory rate limit resets on restart and is per instance


## Roadmap

- Telegram bot reusing `/api/ask`
- The tutor model deciding by itself when to draw
- Two voice audio recap like NotebookLM
- Offline PWA shell
- Better Sarawak Malay and Iban support
