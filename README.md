# Pretty Good AI — Voice Bot

An automated QA testing system that places real phone calls to a hospital front-desk AI agent and simulates realistic patients using GPT-4o-mini. It stress-tests how well the hospital's phone AI handles different caller scenarios — appointment scheduling, cancellations, medication refills, confused callers, and more.

## Architecture

```
┌──────────────┐       ┌──────────────────┐       ┌───────────────────┐
│   Vapi AI    │◄─────►│  FastAPI Server  │◄─────►│ OpenAI GPT-4o-mini│
│ (Call infra) │       │  (main_vapi.py)  │       │ (Patient brain)   │
└──────┬───────┘       └──────────────────┘       └───────────────────┘
       │
       ▼
┌──────────────┐
│   Hospital   │
│  Reception   │
└──────────────┘
```

| Component | Role |
|-----------|------|
| **Vapi AI** | Phone call infrastructure — dialing, audio streaming, STT, TTS |
| **FastAPI Server** | Custom LLM endpoint that Vapi calls each conversation turn; receives webhooks; saves transcripts |
| **GPT-4o-mini** | Generates natural patient responses from scenario-specific system prompts |

## Call Flow

1. `run_calls_vapi.py` triggers an outbound call via the Vapi API → Vapi dials the hospital
2. Hospital receptionist speaks → Vapi transcribes (STT)
3. Vapi sends the conversation to `POST /chat/completions` on the server
4. Server injects the patient scenario system prompt and forwards to GPT-4o-mini
5. GPT-4o-mini generates a patient response → returned to Vapi
6. Vapi converts text to speech (TTS) and plays it to the hospital
7. Repeat until the 3-minute limit or natural call end
8. Vapi sends an `end-of-call-report` webhook → server saves the full transcript as JSON

## Project Structure

```
voice_bot/
├── main_vapi.py          # FastAPI server (Custom LLM endpoint, webhooks, transcript saving)
├── vapi_call_handler.py  # Patient prompt builder and call constants
├── scenarios.py          # 12 predefined patient test scenarios
├── run_calls_vapi.py     # CLI tool to trigger single or batch calls
├── analyze.py            # Transcript analyzer — generates bug reports via GPT-4o-mini
├── requirements.txt      # Python dependencies
├── .env                  # API keys and config (not committed)
└── transcripts/          # Saved call transcripts (JSON)
```

## Setup

### Prerequisites

- Python 3.10+
- A [Vapi AI](https://vapi.ai) account with a phone number
- An [OpenAI](https://platform.openai.com) API key
- An [ngrok](https://ngrok.com) account and auth token

### 1. Clone and install dependencies

```bash
cd voice_bot
python -m venv .venv

# Windows
.\.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure environment variables

Create a `.env` file in the `voice_bot/` directory:

```env
# Vapi AI
VAPI_API_KEY=your_vapi_api_key
VAPI_PHONE_NUMBER_ID=your_vapi_phone_number_id
VAPI_ASSISTANT_ID=your_vapi_assistant_id

# OpenAI
OPENAI_API_KEY=your_openai_api_key

# ngrok
NGROK_AUTH_TOKEN=your_ngrok_auth_token

# Target hospital number
TARGET_PHONE_NUMBER=+1XXXXXXXXXX

# Server
SERVER_PORT=8765
```

### 3. Create a Vapi Assistant

1. Go to the [Vapi Dashboard](https://vapi.ai) → **Assistants**
2. Create a new assistant (any name, e.g. "Patient Simulator")
3. Choose a voice for the patient
4. Copy the **Assistant ID** into your `.env`

> The server auto-configures the assistant on startup — it patches the model provider to `custom-llm`, sets the Custom LLM URL, webhook URL, and server messages automatically.

### 4. Start the server

```bash
python main_vapi.py
```

On startup the server will:
- Start an ngrok tunnel (exposing `localhost:8765`)
- Auto-patch the Vapi assistant to use the Custom LLM endpoint
- Begin listening for Vapi webhooks

### 5. Run calls

```bash
# List all 12 scenarios
python run_calls_vapi.py --list

# Run a single scenario by index
python run_calls_vapi.py --single 0

# Run a batch of calls
python run_calls_vapi.py --batch --count 5 --delay 210

# Run a batch starting from a specific scenario
python run_calls_vapi.py --batch --count 4 --start 6 --delay 210
```

**`--delay`** is the wait time (seconds) between calls. A value of 210 works well — it allows 180s for the call + 30s buffer.

### 6. Analyze transcripts (optional)

```bash
# Analyze all transcripts and generate a bug report
python analyze.py

# Analyze a specific transcript
python analyze.py --file call_20260215_155822_simple_appointment_scheduling.json
```

This sends transcripts to GPT-4o-mini and generates a structured bug report with severity, category, and expected behavior for each issue found.

## Test Scenarios

| # | Scenario | Patient | What It Tests |
|---|----------|---------|---------------|
| 0 | Simple Appointment Scheduling | Sarah Johnson | Basic new-patient scheduling flow |
| 1 | Reschedule Appointment | Michael Chen | Modifying existing appointments |
| 2 | Cancel Appointment | Linda Martinez | Cancellation handling, reluctant caller |
| 3 | Medication Refill Request | Robert Williams | Elderly patient, prescription refill |
| 4 | Office Hours Inquiry | Jessica Taylor | Information queries, follow-up questions |
| 5 | Insurance Inquiry | David Brown | Insurance verification before scheduling |
| 6 | Urgent Symptoms | Amanda Foster | Same-day urgency, anxious caller |
| 7 | Confused Caller | Dorothy Price | Wrong-office edge case, elderly caller |
| 8 | Multiple Requests | Kevin Park | Three tasks in one call |
| 9 | Bilingual Caller | Maria Garcia | Spanish phrases, wrong-department confusion |
| 10 | Interrupting Caller | James Mitchell | Fast-talking, dumps info unprompted |
| 11 | Test Results Inquiry | Susan Lee | Lab results, medical privacy edge case |

## Key Design Decisions

- **Custom LLM via Vapi**: The server registers as an OpenAI-compatible Custom LLM endpoint, giving full control over the system prompt and patient persona per call
- **3-minute max duration**: Enforced via both the Vapi API `maxDurationSeconds` parameter and a live countdown in the patient system prompt
- **Time-aware prompts**: The system prompt includes `remaining_seconds` so GPT-4o-mini naturally wraps up conversations as time runs out
- **Auto-configuration**: On startup, `main_vapi.py` patches the Vapi assistant's model provider, webhook URL, and Custom LLM URL automatically — no manual dashboard setup needed
- **ngrok tunneling**: The server auto-starts an ngrok tunnel so Vapi can reach the local webhooks

## Transcript Format

Each call saves a JSON file to `transcripts/` containing:

```json
{
  "scenario": "Simple Appointment Scheduling",
  "call_id": "019c634c-...",
  "start_time": "2026-02-15T21:55:22Z",
  "end_time": "2026-02-15T21:58:22Z",
  "ended_reason": "assistant-ended-call",
  "cost": 0.15,
  "duration_seconds": 180.0,
  "summary": "...",
  "transcript": "...",
  "messages": [ ... ],
  "recording_url": "https://..."
}
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/chat/completions` | OpenAI-compatible Custom LLM endpoint (called by Vapi) |
| `POST` | `/vapi/webhook` | Receives Vapi server messages (status updates, end-of-call reports) |
| `POST` | `/set-scenario` | Set the scenario index for the next call |
| `POST` | `/make-call` | Trigger an outbound call via Vapi API |
| `GET`  | `/transcripts` | List all saved transcripts |
| `GET`  | `/transcripts/{filename}` | Get a specific transcript |
| `GET`  | `/` | Server status and info |

