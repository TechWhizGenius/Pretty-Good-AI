"""
Pretty Good AI - Voice Bot Challenge (Vapi AI Version)

Architecture:
  Vapi  → handles phone call, STT, TTS
  This server → Custom LLM endpoint (OpenAI-compatible)
  GPT-4o-mini → generates patient responses via our system prompt

Flow:
  1. Vapi places outbound call to hospital reception
  2. Hospital receptionist speaks → Vapi transcribes (STT)
  3. Vapi sends conversation to our /chat/completions endpoint
  4. We inject patient scenario system prompt, call GPT-4o-mini
  5. Return response → Vapi converts to speech (TTS)
  6. Repeat until call ends (max 2 minutes)
"""

import os
import json
import logging
import time
import uuid
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from dotenv import load_dotenv
import httpx
from pyngrok import ngrok, conf
from openai import AsyncOpenAI

from vapi_call_handler import build_patient_system_prompt, MAX_CALL_DURATION_SECONDS
from scenarios import SCENARIOS

load_dotenv()

# --- Config ---
VAPI_API_KEY = os.getenv("VAPI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8765"))
NGROK_AUTH_TOKEN = os.getenv("NGROK_AUTH_TOKEN")
VAPI_ASSISTANT_ID = os.getenv("VAPI_ASSISTANT_ID")
SERVER_DOMAIN = os.getenv("SERVER_DOMAIN")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Voice Bot - Pretty Good AI Challenge (Vapi AI)")

# OpenAI client for GPT-4o-mini patient responses
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Track active calls: call_id -> {"scenario": dict, "start_time": datetime}
active_calls: dict[str, dict] = {}
call_results: list[dict] = []

# Scenario rotation
_scenario_index = 0


# ──────────────────────────────────────────────────────────────
#  Lifecycle
# ──────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    """Start ngrok tunnel and auto-configure the Vapi assistant."""
    global SERVER_DOMAIN

    if SERVER_DOMAIN:
        logger.info(f"Using manually configured SERVER_DOMAIN: {SERVER_DOMAIN}")
    else:
        # Kill any stale ngrok processes before starting a new tunnel
        try:
            ngrok.kill()
        except Exception:
            pass

        # Start ngrok tunnel
        if NGROK_AUTH_TOKEN:
            conf.get_default().auth_token = NGROK_AUTH_TOKEN
        else:
            logger.warning("NGROK_AUTH_TOKEN not set. ngrok may fail.")

        try:
            public_url = ngrok.connect(SERVER_PORT, "http").public_url
            SERVER_DOMAIN = public_url.replace("https://", "").replace("http://", "")
            logger.info(f"ngrok tunnel started: {public_url}")
            logger.info(f"SERVER_DOMAIN: {SERVER_DOMAIN}")
        except Exception as e:
            logger.error(f"Failed to start ngrok: {e}")
            raise

    logger.info(f"Custom LLM URL:  https://{SERVER_DOMAIN}/chat/completions")
    logger.info(f"Webhook URL:     https://{SERVER_DOMAIN}/vapi/webhook")

    # Auto-configure the Vapi assistant to use our Custom LLM
    await update_vapi_assistant()


@app.on_event("shutdown")
async def shutdown_event():
    """Close ngrok tunnel on server shutdown."""
    try:
        ngrok.disconnect_all()
        ngrok.kill()
        logger.info("ngrok tunnel closed.")
    except Exception:
        pass


async def update_vapi_assistant():
    """
    Patch the Vapi assistant so it routes all LLM calls through our
    Custom LLM endpoint instead of using its own built-in model.
    Also sets it to wait for the hospital receptionist to speak first.
    """
    if not all([VAPI_ASSISTANT_ID, VAPI_API_KEY, SERVER_DOMAIN]):
        logger.warning("Skipping Vapi assistant update (missing VAPI_ASSISTANT_ID / VAPI_API_KEY / SERVER_DOMAIN)")
        return

    custom_llm_url = f"https://{SERVER_DOMAIN}/chat/completions"
    webhook_url = f"https://{SERVER_DOMAIN}/vapi/webhook"

    try:
        async with httpx.AsyncClient() as client:
            patch_payload = {
                "model": {
                    "provider": "custom-llm",
                    "url": custom_llm_url,
                    "model": "gpt-4o-mini",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a patient calling a hospital.",
                        }
                    ],
                },
                "server": {
                    "url": webhook_url,
                    "timeoutSeconds": 20,
                },
                # Explicitly ensure end-of-call-report is in serverMessages
                "serverMessages": [
                    "end-of-call-report",
                    "status-update",
                    "speech-update",
                    "conversation-update",
                    "hang",
                ],
                # Patient waits for hospital to answer and greet first
                "firstMessageMode": "assistant-waits-for-user",
                # Remove any pre-configured firstMessage so Custom LLM drives all replies
                "firstMessage": "",
            }
            logger.info(f"Patching Vapi assistant {VAPI_ASSISTANT_ID}...")
            logger.info(f"  model.provider  = custom-llm")
            logger.info(f"  model.url       = {custom_llm_url}")
            logger.info(f"  server.url      = {webhook_url}")
            logger.info(f"  serverMessages  = {patch_payload['serverMessages']}")

            response = await client.patch(
                f"https://api.vapi.ai/assistant/{VAPI_ASSISTANT_ID}",
                headers={
                    "Authorization": f"Bearer {VAPI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=patch_payload,
                timeout=15.0,
            )
            response.raise_for_status()
            result = response.json()

            # Verify the update took effect
            actual_provider = result.get("model", {}).get("provider", "???")
            actual_model_url = result.get("model", {}).get("url", "???")
            actual_server_url = result.get("server", {}).get("url", "???")
            actual_server_msgs = result.get("serverMessages", [])

            logger.info(f"✓ Vapi assistant updated successfully!")
            logger.info(f"  Verified model.provider  = {actual_provider}")
            logger.info(f"  Verified model.url       = {actual_model_url}")
            logger.info(f"  Verified server.url      = {actual_server_url}")
            logger.info(f"  Verified serverMessages  = {actual_server_msgs}")

            if actual_provider != "custom-llm":
                logger.error(f"  MISMATCH: model.provider is '{actual_provider}', expected 'custom-llm'!")
            if "end-of-call-report" not in actual_server_msgs:
                logger.error(f"  ✗ MISMATCH: 'end-of-call-report' missing from serverMessages!")

    except httpx.HTTPStatusError as e:
        logger.error(f"Failed to update Vapi assistant (HTTP {e.response.status_code}): {e.response.text}")
    except Exception as e:
        logger.error(f"Failed to update Vapi assistant: {e}")
        logger.info("You may need to manually set the assistant model to 'custom-llm'")
        logger.info(f"  Custom LLM URL: {custom_llm_url}")


# ──────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────

def get_next_scenario() -> dict:
    global _scenario_index
    scenario = SCENARIOS[_scenario_index % len(SCENARIOS)]
    _scenario_index += 1
    logger.info(f"Assigned scenario: {scenario['name']}")
    return scenario


def save_transcript(result: dict):
    """Save call transcript / end-of-call report to a JSON file."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = result.get("scenario", "unknown").replace(" ", "_").lower()
    filename = f"transcripts/call_{ts}_{name}.json"
    filepath = Path(filename)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(result, f, indent=2, default=str)
    logger.info(f"Transcript saved: {filename}")


# ──────────────────────────────────────────────────────────────
#  Custom LLM endpoint  (OpenAI Chat Completion compatible)
# ──────────────────────────────────────────────────────────────

@app.post("/chat/completions")
async def custom_llm(request: Request):
    """
    OpenAI-compatible endpoint that Vapi calls for every LLM turn.
    We swap the system prompt with our patient scenario and forward to GPT-4o-mini.
    """
    try:
        body = await request.json()
        logger.info("Custom LLM request received")

        # --- identify the call & assign a scenario ---
        call_info = body.get("call", {})
        call_id = call_info.get("id", "unknown")

        if call_id not in active_calls:
            scenario = get_next_scenario()
            active_calls[call_id] = {
                "scenario": scenario,
                "start_time": datetime.now(),
            }
            logger.info(f"Call {call_id} → scenario: {scenario['name']}")

        call_data = active_calls[call_id]
        scenario = call_data["scenario"]
        start_time = call_data["start_time"]

        # --- build patient system prompt with remaining time ---
        elapsed = (datetime.now() - start_time).total_seconds()
        remaining = max(0, int(MAX_CALL_DURATION_SECONDS - elapsed))
        patient_system = build_patient_system_prompt(scenario, remaining)

        # --- replace system message from Vapi with our patient prompt ---
        messages = body.get("messages", [])
        patient_messages = []
        replaced = False
        for msg in messages:
            if msg.get("role") == "system" and not replaced:
                patient_messages.append({"role": "system", "content": patient_system})
                replaced = True
            else:
                patient_messages.append(msg)
        if not replaced:
            patient_messages.insert(0, {"role": "system", "content": patient_system})

        # --- streaming vs non-streaming ---
        if body.get("stream", False):
            return StreamingResponse(
                _stream_response(patient_messages),
                media_type="text/event-stream",
            )
        else:
            response = await openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=patient_messages,
                max_tokens=150,
                temperature=0.8,
            )
            result = response.model_dump()
            content = result["choices"][0]["message"]["content"]
            logger.info(f"[Patient] {content}")
            return JSONResponse(result)

    except Exception as e:
        logger.error(f"Custom LLM error: {e}", exc_info=True)
        # Return a valid OpenAI-format fallback so Vapi doesn't break
        return JSONResponse({
            "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "gpt-4o-mini",
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": "I'm sorry, could you repeat that?"},
                "finish_reason": "stop",
            }],
        })


async def _stream_response(messages: list[dict]):
    """Stream GPT-4o-mini response back to Vapi in SSE format."""
    try:
        stream = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=150,
            temperature=0.8,
            stream=True,
        )
        full_text = ""
        async for chunk in stream:
            data = chunk.model_dump()
            if chunk.choices and chunk.choices[0].delta.content:
                full_text += chunk.choices[0].delta.content
            yield f"data: {json.dumps(data)}\n\n"

        yield "data: [DONE]\n\n"

        if full_text:
            logger.info(f"[Patient] {full_text}")
    except Exception as e:
        logger.error(f"Streaming error: {e}", exc_info=True)
        fallback = {
            "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": "gpt-4o-mini",
            "choices": [{
                "index": 0,
                "delta": {"content": "I'm sorry, could you repeat that?"},
                "finish_reason": "stop",
            }],
        }
        yield f"data: {json.dumps(fallback)}\n\n"
        yield "data: [DONE]\n\n"


# ──────────────────────────────────────────────────────────────
#  Vapi Webhooks  (call lifecycle + transcript saving)
# ──────────────────────────────────────────────────────────────

@app.post("/vapi/webhook")
async def vapi_webhook(request: Request):
    """
    Handle Vapi server messages:
      - status-update       → log call status changes
      - end-of-call-report  → save full transcript from Vapi
    """
    try:
        body = await request.json()
        message = body.get("message", body)
        event_type = message.get("type", "")

        logger.info(f"Webhook received: type={event_type}")

        if event_type == "end-of-call-report":
            logger.info(">>> end-of-call-report received — processing transcript...")

            call = message.get("call", {})
            call_id = call.get("id", "unknown")
            logger.info(f"    call_id: {call_id}")
            logger.info(f"    active_calls tracked: {list(active_calls.keys())}")

            # Look up scenario name from our tracking
            scenario_name = "unknown"
            if call_id in active_calls:
                scenario_name = active_calls[call_id]["scenario"]["name"]
                del active_calls[call_id]
                logger.info(f"    scenario matched: {scenario_name}")
            else:
                logger.warning(f"    call_id not found in active_calls, scenario will be 'unknown'")

            # Save everything Vapi gives us
            transcript_text = message.get("transcript", "")
            artifact_messages = message.get("artifact", {}).get("messages", [])
            logger.info(f"    transcript length: {len(transcript_text) if transcript_text else 0} chars")
            logger.info(f"    artifact messages: {len(artifact_messages)} entries")

            transcript_data = {
                "scenario": scenario_name,
                "call_id": call_id,
                "start_time": call.get("startedAt"),
                "end_time": call.get("endedAt"),
                "ended_reason": message.get("endedReason") or call.get("endedReason"),
                "cost": message.get("cost") or call.get("cost"),
                "duration_seconds": None,
                "summary": message.get("summary"),
                "transcript": transcript_text,
                "messages": artifact_messages,
                "recording_url": message.get("recordingUrl"),
            }

            # Calculate duration
            try:
                started = call.get("startedAt") or message.get("startedAt")
                ended = call.get("endedAt") or message.get("endedAt")
                if started and ended:
                    start_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
                    end_dt = datetime.fromisoformat(ended.replace("Z", "+00:00"))
                    transcript_data["duration_seconds"] = (end_dt - start_dt).total_seconds()
                    logger.info(f"    duration: {transcript_data['duration_seconds']:.1f}s")
            except Exception as e:
                logger.warning(f"    Could not calculate duration: {e}")

            call_results.append(transcript_data)
            save_transcript(transcript_data)
            logger.info(f">>> Transcript SAVED for call {call_id}")

        elif event_type == "status-update":
            call = message.get("call", {})
            status = message.get("status") or call.get("status")
            logger.info(f"Call {call.get('id')} → status: {status}")

        elif event_type == "hang":
            logger.info("Call hang event received")

        elif event_type == "conversation-update":
            # Silently acknowledge — no action needed
            pass

        else:
            logger.info(f"Unhandled webhook type: {event_type}")

        return JSONResponse({"status": "ok"})

    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────────────────────
#  Utility endpoints
# ──────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "status": "running",
        "active_calls": len(active_calls),
        "platform": "vapi",
        "server_domain": SERVER_DOMAIN,
    }


@app.post("/set-scenario")
async def set_scenario(request: Request):
    """Set the scenario index for the next call."""
    global _scenario_index
    body = await request.json()
    idx = body.get("scenario_index", 0)
    _scenario_index = idx
    scenario = SCENARIOS[idx % len(SCENARIOS)]
    logger.info(f"Scenario index set to {idx}: {scenario['name']}")
    return {"scenario_index": idx, "scenario_name": scenario["name"]}


@app.post("/make-call")
async def trigger_call(request: Request):
    """HTTP endpoint to trigger an outbound call via Vapi API."""
    try:
        body = await request.json() if request.headers.get("content-type") == "application/json" else {}
        scenario_index = body.get("scenario_index")
        target_number = body.get("target_number", os.getenv("TARGET_PHONE_NUMBER"))

        if not VAPI_API_KEY:
            raise HTTPException(status_code=500, detail="VAPI_API_KEY not set")

        global _scenario_index
        if scenario_index is not None:
            _scenario_index = scenario_index

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.vapi.ai/call",
                headers={
                    "Authorization": f"Bearer {VAPI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "phoneNumberId": os.getenv("VAPI_PHONE_NUMBER_ID"),
                    "customer": {
                        "number": target_number,  # Hospital reception number
                    },
                    "assistantId": VAPI_ASSISTANT_ID,
                    "maxDurationSeconds": MAX_CALL_DURATION_SECONDS,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            call_data = response.json()

        logger.info(f"Call initiated: {call_data.get('id')} → {target_number}")
        return {"call_id": call_data.get("id"), "target": target_number}

    except Exception as e:
        logger.error(f"Error making call: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/transcripts")
async def list_transcripts():
    """List all saved transcripts."""
    transcript_dir = Path("transcripts")
    if not transcript_dir.exists():
        return {"transcripts": []}
    files = sorted(transcript_dir.glob("*.json"), reverse=True)
    return {"transcripts": [f.name for f in files]}


@app.get("/transcripts/{filename}")
async def get_transcript(filename: str):
    """Get a specific transcript."""
    filepath = Path(f"transcripts/{filename}")
    if not filepath.exists():
        return {"error": "not found"}
    with open(filepath) as f:
        return json.load(f)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT)
