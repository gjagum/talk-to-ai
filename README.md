# 🗣️ Talk to AI — Voice AI Agent Demo

A full-stack proof of concept for building a **conversational voice AI agent** that you can actually *talk* to. Speak into your browser, the AI listens, thinks, and talks back — in real time, with natural turn-taking.

Built as a vertical-slice architecture demo comparing three delivery styles of the same STT → LLM → TTS pipeline:

| Mode | Transport | Providers |-latency feel|
|------|-----------|-----------|-------------|
| **Realtime** | WebSocket ↔ OpenAI Realtime API | OpenAI (STT + GPT + TTS) | Sub-second, interruptible |
| **Talk** | WebSocket ↔ Deepgram Voice Agent API | Deepgram nova-3 + OpenAI + Aura-2 | Sub-second, barge-in support |
| **Whisper** | HTTP request/response loop | OpenAI Whisper + GPT + OpenAI TTS *or* Deepgram variant | Step-by-step, easiest to debug |

---

## 🏗️ Architecture

```
┌──────────────────────┐         ┌──────────────────────┐
│   React + Vite FE    │  WS/HTTP │   FastAPI Backend    │
│  (Tailwind, lucide)  │ ◄──────► │  (vertical slices)   │
└──────────────────────┘         └──────────┬───────────┘
                                            │ WS / HTTP
                          ┌─────────────────┼──────────────────┐
                          ▼                 ▼                  ▼
                 OpenAI Realtime   Deepgram Agent API   OpenAI/Deepgram
                                                          REST APIs
```

### Backend (`backend/`)
A FastAPI app organized by **feature slices** — each feature owns its router + services, mounted under its own URL prefix.

```
backend/
├── requirements.txt
└── app/
    ├── main.py                 # FastAPI app + CORS + router mounts
    ├── core/config.py          # Env-based config (keys, history limit)
    ├── features/
    │   ├── agent/              # 🌟 Deepgram Voice Agent WebSocket relay
    │   │   ├── relay.py        #   proxies browser ↔ wss://agent.deepgram.com
    │   │   ├── router.py       #   /api/agent/ws
    │   │   └── settings.py     #   persona + Deepgram Settings payload builder
    │   ├── realtime/           # OpenAI Realtime WebSocket relay
    │   │   ├── relay.py
    │   │   └── router.py       #   /api/realtime/ws
    │   └── voice/              # HTTP STT→LLM→TTS pipeline
    │       ├── router.py       #   /api/voice/process, /deepgram/process, ...
    │       └── services/
    │           ├── stt.py / deepgram_stt.py
    │           ├── llm.py
    │           └── tts.py / deepgram_tts.py
    └── routes/agent.py         # (alt wiring kept for reference)
```

### Frontend (`frontend/`)
React 18 + Vite + TailwindCSS dashboard letting you switch between three UIs:

- `RealtimeAgent.jsx` — streaming WebSocket demo (OpenAI Realtime)
- `TalkAgent.jsx` — streaming WebSocket demo (Deepgram Voice Agent)
- `WhisperAgent.jsx` — record → upload → play loop (HTTP pipeline)
- `ConversationLog.jsx` — shared transcript view
- `VoiceRecorder.jsx` — mic capture (native / PCM)

---

## 🚀 Quick Start

### 1. Prerequisites
- Python **3.11+**
- Node.js **18+**
- API keys for:
  - **OpenAI** (`OPENAI_API_KEY`) — required for all three modes
  - **Deepgram** (`DEEPGRAM_API_KEY`) — required for Talk mode + Deepgram Whisper variant

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Create .env with your keys
cat > .env <<'EOF'
OPENAI_API_KEY=sk-...
DEEPGRAM_API_KEY=...
MAX_CONVERSATION_HISTORY=10
EOF

# Run the API (FastAPI with standard server)
fastapi dev app/main.py              # or: uvicorn app.main:app --reload
# Backend lives at http://localhost:8000
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
# UI lives at http://localhost:5173
```

Open the UI, pick an agent mode, allow mic access, and start talking. 🎙️

---

## 🔌 API Reference

### WebSocket streaming
| Endpoint | Protocol | Upstream |
|----------|----------|----------|
| `ws://localhost:8000/api/agent/ws`     | Binary PCM16 @ 24kHz + JSON events | Deepgram Voice Agent API |
| `ws://localhost:8000/api/realtime/ws`  | base64 audio in JSON events         | OpenAI Realtime API |

The browser streams mic audio up; the relay forwards it upstream and pipes the AI's audio frames + transcript events straight back down.

### HTTP request/response (Whisper mode)
| Endpoint | Description |
|----------|-------------|
| `POST /api/voice/process`              | OpenAI STT → GPT → OpenAI TTS (multipart audio upload) |
| `POST /api/voice/deepgram/process`     | Deepgram STT → GPT → Aura-2 TTS |
| `GET  /api/voice/greeting`             | OpenAI TTS greeting |
| `GET  /api/voice/deepgram/greeting`    | Aura-2 TTS greeting |

The HTTP responses return `audio/mpeg` with the transcript exposed in the `X-Transcript` / `X-Response` headers.

---

## 🧠 Persona

The default persona bundled in `frontend/src/App.jsx` is **Ryan**, an AI receptionist for *Kinetic Innovative Staffing* — greeting inbound callers, explaining the value prop, and booking discovery calls. Swap `DEFAULT_PERSONA` for your own use case.

---

## 🔧 Tech Stack

**Backend:** FastAPI 0.138 · Uvicorn · `openai` SDK · `deepgram-sdk` 7.3.1 · `python-dotenv` · `websockets`

**Frontend:** React 18 · Vite 4 · TailwindCSS 3 · lucide-react · native Web Audio + WebSocket APIs

---

## 📝 Notes

- The Deepgram Voice Agent relay uses **raw binary PCM frames** (no base64 wrapping), which is cleaner than OpenAI Realtime's JSON-wrapped audio.
- For the OpenAI LLM inside Deepgram's pipeline, `Settings.agent.think.endpoint` is set with the caller's OpenAI key so calls bill to your OpenAI account (not Deepgram's).
- CORS is preconfigured to allow `localhost:3000`, `3001`, `5173`, and `127.0.0.1:3001`.

---

## 📄 License

Proof of concept — provided as-is for demo / learning purposes.
