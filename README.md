# AjarLok

Snap it, say it or type it. A STEM tutor that speaks your language and barely touches your data plan.

Live demo at <CLOUD_RUN_URL>

Built in 90 minutes by Stuff (Lawrence Lian Anak Matius Ding, Cyndia Ya Aii Teo, Noah Ting Ding Ka, Nor Syuhada Binti Hamdan) at the IT Week mini hackathon, organised by UNIMAS FCSIT and co organised by IEEE UNIMAS Student Branch, Google Antigravity workshop.

Problem statement "Localized and Inclusive STEM Learning Agent"


## The problem

A Form 2 student in a longhouse up the Rajang has one bar of signal, RM10 of prepaid data, a hand me down phone and a Science textbook that is not in the language spoken at home.

Every AI tutor out there assumes fast WiFi, a new phone, fluent English and a login. For this student, AI tutoring is a loading spinner.


## Our solution

AjarLok ("ajar" means teach, "lok" is Sarawak Malay slang) adapts to the student instead of the other way round.

- Three big buttons
	- Ambil Gambar (Snap) always opens the camera
	- Muat Naik (Upload) always opens the gallery
	- Cakap (Talk) records a voice question
- A text box that is always visible, where images can also be pasted or dragged and dropped on a laptop
- Answers in the student's own language, including mixed Bahasa Melayu and English
- Button labels follow the device language
	- Malay devices show Malay first with English underneath
	- Other devices show English first with Malay underneath
- Pitched to the student's level, from Darjah 1 to university, by simply saying "saya darjah 5" or "I am 15"
- Local examples such as padi fields, longhouses, the Bakun dam and kek lapis
- One tap follow ups on every answer, labelled in the language of the answer
	- Dengar (Listen)
	- Lukis (Draw) makes a small step by step SVG diagram, also drawn automatically when the student asks for one
	- Senangkan (Simpler)
	- Contoh Tempatan (Local Example)
	- Kuiz Saya (Quiz Me)
- Jimat Data mode
	- Detects a weak connection
	- Shrinks photos and voice on the phone before upload
	- Sends short text answers read aloud by the phone's own voice at zero data cost
	- Shows how much data every answer used
- Safe for children
	- IC numbers, phone numbers, emails and card numbers are hidden on the phone before sending
	- The tutor never asks for personal details and points to Talian Kasih 15999 when a student is in distress
- No account, no install, just a link


## Documentation

- [System Design](docs/system_design.md)


## Run locally

```bash
cp .env.example .env
pip install -r requirements.txt
uvicorn app.main:app --reload
```


## Submission

### Project Name

AjarLok

### Brief Description

AjarLok is a STEM and IT tutor built for the student AI forgot. Picture a Form 2 student in a Sarawak longhouse with one bar of signal, RM10 of prepaid data and a textbook that is not in their home language. With AjarLok they snap a photo of the question, say it out loud or type it, in Bahasa Melayu, Sarawak Malay, English, Mandarin or a mix. AjarLok answers in the same language, pitched at their level from Darjah 1 to university, using things they know like kek lapis, padi fields and the Rajang River. It runs in any phone browser with no account and no install. The whole app is under 20 KB, a typical answer costs less than 1 KB and answers are read aloud with the phone's own voice at zero data cost. Gemini 3.8 Flash understands photos and voice, ILMU, the Malaysian language model by YTL AI Labs, writes the lesson, and Qwen 27B and Gemini stand by as fallbacks. Hosted on Google Cloud Run in Singapore, close to Sarawak.

### Uniqueness

1. Built around data cost. The phone checks the connection, picks Lite, Standard or Full mode, shrinks photos and records low bitrate voice before upload. Every answer shows its KB used and diagrams are 5 KB SVG.
2. Local, not just translated. ILMU, a Malaysian model, replies in the student's language and code switching, follows KSSR and KSSM and explains with Sarawak life, not Western examples.
3. Adapts to age, no account. Saying "saya 12 tahun" or "Form 4" once adjusts every answer. Nothing is stored on a server.
4. Safe by default. IC numbers, phone numbers and emails are hidden on the phone before sending, and the child safe tutor gives Talian Kasih 15999 to students in distress.
5. Made for first time users. Big Snap, Upload and Talk buttons in the phone's language and one tap follow ups like Senangkan and Kuiz Saya, so students rarely type.
6. Inspired by NotebookLM. A photo of the student's own textbook page becomes the lesson, and Kuiz Saya makes practice questions.

### Deployed Project Link

<CLOUD_RUN_URL>
