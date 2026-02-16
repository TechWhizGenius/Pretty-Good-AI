"""
CLI runner for the voice bot using Vapi AI.
Usage:
    python run_calls_vapi.py --single 0       # Run a single scenario (by index)
    python run_calls_vapi.py --batch           # Run all scenarios
    python run_calls_vapi.py --batch --count 5 # Run first 5 scenarios
    python run_calls_vapi.py --list            # List available scenarios
"""

import argparse
import asyncio
import os
import sys

import httpx
from dotenv import load_dotenv

from scenarios import SCENARIOS
from vapi_call_handler import MAX_CALL_DURATION_SECONDS

load_dotenv()

VAPI_API_KEY = os.getenv("VAPI_API_KEY")
TARGET_PHONE_NUMBER = os.getenv("TARGET_PHONE_NUMBER", "+16156451400")  # Hospital reception
SERVER_DOMAIN = os.getenv("SERVER_DOMAIN")
VAPI_PHONE_NUMBER_ID = os.getenv("VAPI_PHONE_NUMBER_ID")
VAPI_ASSISTANT_ID = os.getenv("VAPI_ASSISTANT_ID")
SERVER_PORT = os.getenv("SERVER_PORT", "8765")


async def get_server_domain() -> str:
    """Get SERVER_DOMAIN from .env or fetch it from the running server (ngrok URL)."""
    global SERVER_DOMAIN
    if SERVER_DOMAIN:
        return SERVER_DOMAIN
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"http://localhost:{SERVER_PORT}/", timeout=5.0)
            resp.raise_for_status()
            data = resp.json()
            SERVER_DOMAIN = data.get("server_domain")
            if SERVER_DOMAIN:
                print(f"   Fetched SERVER_DOMAIN from running server: {SERVER_DOMAIN}")
                return SERVER_DOMAIN
    except Exception as e:
        print(f"   [Warning] Could not fetch SERVER_DOMAIN from server: {e}")
    print("   [Error] SERVER_DOMAIN is not set and could not be fetched from server.")
    print("   Make sure the server (main_vapi.py) is running first.")
    sys.exit(1)


async def set_scenario_on_server(scenario_index: int):
    """Tell the running server which scenario to use for the next call."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"http://localhost:{SERVER_PORT}/make-call",
                json={"scenario_index": scenario_index, "dry_run": True},
                timeout=5.0,
            )
            # We don't actually trigger via this endpoint; we just set the index.
            # The server rotates scenarios, and we set _scenario_index via make-call.
    except Exception:
        pass  # If this fails, the server will just use its rotation


def list_scenarios():
    print("\nAvailable Scenarios:")
    print("-" * 60)
    for i, s in enumerate(SCENARIOS):
        print(f"  [{i}] {s['name']}")
        print(f"      Patient: {s['patient_name']}")
        print(f"      {s['description']}")
        print()


async def make_call(scenario_index: int):
    """Make a single outbound call using Vapi API."""
    scenario = SCENARIOS[scenario_index]
    await get_server_domain()

    print(f"\n[Call] Calling {TARGET_PHONE_NUMBER} with scenario: {scenario['name']}")
    print(f"   Patient: {scenario['patient_name']}")
    print(f"   Max duration: {MAX_CALL_DURATION_SECONDS}s")

    async with httpx.AsyncClient() as client:
        try:
            # Tell server which scenario index to use next
            try:
                await client.post(
                    f"http://localhost:{SERVER_PORT}/set-scenario",
                    json={"scenario_index": scenario_index},
                    timeout=5.0,
                )
            except Exception:
                pass  # Endpoint might not exist; server uses rotation

            response = await client.post(
                "https://api.vapi.ai/call",
                headers={
                    "Authorization": f"Bearer {VAPI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "phoneNumberId": VAPI_PHONE_NUMBER_ID,
                    "customer": {
                        "number": TARGET_PHONE_NUMBER,  # Hospital reception number
                    },
                    "assistantId": VAPI_ASSISTANT_ID,
                    "maxDurationSeconds": MAX_CALL_DURATION_SECONDS,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            call_data = response.json()
            call_id = call_data.get("id")
            print(f"   Call ID: {call_id}")
            return call_id
        except httpx.HTTPStatusError as e:
            print(f"   [Error] HTTP {e.response.status_code}: {e.response.text}")
            return None
        except Exception as e:
            print(f"   [Error] {e}")
            return None


async def run_batch(count: int, delay: int, start: int = 0):
    """Run a batch of calls with delay between each."""
    end = min(start + count, len(SCENARIOS))
    total = end - start
    print(f"\n[Batch] Starting batch of {total} calls (scenarios {start}-{end - 1}, delay: {delay}s between calls)")
    print(f"   Max call duration: {MAX_CALL_DURATION_SECONDS}s")
    print("=" * 60)

    call_ids = []
    for i in range(start, end):
        call_id = await make_call(i)
        if call_id:
            call_ids.append(call_id)

        if i < end - 1:
            print(f"\n[Wait] Waiting {delay}s before next call...")
            await asyncio.sleep(delay)

    print("\n" + "=" * 60)
    print(f"[Done] {len(call_ids)}/{total} calls initiated!")
    print("\nCall IDs:")
    for call_id in call_ids:
        print(f"  - {call_id}")


def main():
    parser = argparse.ArgumentParser(description="Voice Bot Call Runner (Vapi AI)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--single", type=int, metavar="INDEX", help="Run a single scenario by index")
    group.add_argument("--batch", action="store_true", help="Run all scenarios")
    group.add_argument("--list", action="store_true", help="List available scenarios")

    parser.add_argument("--count", type=int, default=len(SCENARIOS), help="Number of scenarios to run in batch mode")
    parser.add_argument("--start", type=int, default=0, help="Starting scenario index for batch mode (default: 0)")
    parser.add_argument("--delay", type=int, default=45, help="Delay in seconds between calls (default: 45)")

    args = parser.parse_args()

    # Validate environment
    if not args.list:
        missing = []
        for var in ["VAPI_API_KEY", "VAPI_PHONE_NUMBER_ID", "VAPI_ASSISTANT_ID"]:
            if not os.getenv(var):
                missing.append(var)
        if missing:
            print(f"[Error] Missing environment variables: {', '.join(missing)}")
            print("   Please set them in your .env file")
            sys.exit(1)

    if args.list:
        list_scenarios()
    elif args.single is not None:
        if 0 <= args.single < len(SCENARIOS):
            asyncio.run(make_call(args.single))
        else:
            print(f"[Error] Invalid scenario index. Must be 0-{len(SCENARIOS) - 1}")
            sys.exit(1)
    elif args.batch:
        asyncio.run(run_batch(args.count, args.delay, args.start))


if __name__ == "__main__":
    main()
