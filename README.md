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

- Three ways in
	- Ambil Gambar to photograph a textbook question
	- Cakap to ask out loud
	- Taip to type
- Answers in the student's own language, including mixed Bahasa Melayu and English
- Button labels follow the device language
	- Malay devices show Malay first with English underneath
	- Other devices show English first with Malay underneath
- Pitched to the student's level, from Darjah 1 to university, by simply saying "saya darjah 5" or "I am 15"
- Local examples such as padi fields, longhouses, the Bakun dam and kek lapis
- Jimat Data mode
	- Detects a weak connection
	- Shrinks photos and voice on the phone before upload
	- Sends short text answers read aloud by the phone's own voice at zero data cost
	- Shows how much data every answer used
- One tap follow ups Lebih Mudah, Contoh Tempatan and Kuiz Saya
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

AjarLok is a lightweight, voice first STEM and IT tutor for students in rural Sarawak and anyone learning outside their first language. Students snap a photo of a textbook question, record a voice question or type, in Bahasa Melayu, Sarawak Malay, English, Mandarin or a mix of them. They get an explanation pitched at their level, from Darjah 1 to university, using local examples like padi fields, longhouses and the Rajang River. It is built for cheap phones and weak signals. The app checks the connection, compresses photos and voice on the phone before upload, keeps answers as short as needed and reads them aloud with the phone's own voice so audio costs no data. There is no account and nothing to install. Gemini 3.8 Flash reads photos and voice notes, ILMU, a Malaysian language model by YTL AI Labs, writes the answer, and Qwen 27B from SovernStack and Gemini stand by as fallbacks. It runs on Google Cloud Run in Singapore, close to Sarawak.

### Uniqueness

1. Bandwidth aware by design. An Input Gate on the phone picks a Lite, Standard or Full mode from the live connection, shrinks images and audio before upload and shapes the reply to match. Every answer shows how much data it used.
2. Local, not just translated. Answers follow the student's language and code switching, are pitched to Malaysian KSSR and KSSM levels, and explain with Sarawak examples. The tutor model is ILMU, built for Malaysian languages.
3. Level adaptive without accounts. A student states their age or school year once and every answer adjusts. Nothing is stored on a server.
4. Built for first time users. One screen, three big buttons and one tap follow ups mean students rarely need to type.
5. Inspired by NotebookLM. A photo of the student's own textbook page becomes the lesson source, and Kuiz Saya turns it into practice questions.

### Deployed Project Link

<CLOUD_RUN_URL>
