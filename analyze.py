"""
Transcript Analyzer - Reviews call transcripts and identifies bugs/issues.
Generates a bug report from all transcripts.

Usage:
    python analyze.py                    # Analyze all transcripts
    python analyze.py --file <filename>  # Analyze a specific transcript
"""

import argparse
import json
import os
from pathlib import Path
from datetime import datetime

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TRANSCRIPTS_DIR = Path("transcripts")


def load_transcripts(specific_file: str = None) -> list[dict]:
    """Load transcript files."""
    if specific_file:
        filepath = TRANSCRIPTS_DIR / specific_file
        if filepath.exists():
            with open(filepath) as f:
                return [json.load(f)]
        else:
            print(f"File not found: {filepath}")
            return []

    transcripts = []
    if TRANSCRIPTS_DIR.exists():
        for f in sorted(TRANSCRIPTS_DIR.glob("*.json")):
            with open(f) as fh:
                data = json.load(fh)
                data["_filename"] = f.name
                transcripts.append(data)
    return transcripts


def format_transcript(t: dict) -> str:
    """Format a transcript for analysis."""
    lines = [f"Scenario: {t.get('scenario', 'Unknown')}"]
    lines.append(f"Duration: {t.get('duration_seconds', 'N/A')}s")
    lines.append(f"Turns: {t.get('turn_count', 'N/A')}")
    lines.append("")

    for entry in t.get("transcript", []):
        role = "AGENT" if entry["role"] == "agent" else "PATIENT"
        lines.append(f"[{role}]: {entry['text']}")

    return "\n".join(lines)


def analyze_transcripts(transcripts: list[dict]) -> str:
    """Use GPT-4o-mini to analyze transcripts and find bugs."""
    formatted = []
    for i, t in enumerate(transcripts, 1):
        formatted.append(f"=== CALL {i} ===")
        formatted.append(format_transcript(t))
        formatted.append("")

    all_transcripts = "\n".join(formatted)

    prompt = f"""You are a QA analyst reviewing call transcripts between an AI medical office agent and simulated patients.

Analyze these transcripts and produce a detailed bug report. For each issue, provide:
- **Bug ID**: B001, B002, etc.
- **Severity**: Critical / High / Medium / Low
- **Category**: One of [Incorrect Response, Hallucination, Failure to Understand, Awkward Phrasing, Missing Feature, Logic Error, Conversation Flow]
- **Call**: Which call/scenario it occurred in
- **Description**: What happened
- **Expected Behavior**: What should have happened
- **Transcript Excerpt**: The relevant part of the conversation

Also provide a summary at the top with:
- Total calls analyzed
- Total bugs found by severity
- Overall quality assessment

Here are the transcripts:

{all_transcripts}

Generate a comprehensive bug report in Markdown format."""

    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4096,
        temperature=0.3,
    )

    return response.choices[0].message.content


def main():
    parser = argparse.ArgumentParser(description="Analyze call transcripts")
    parser.add_argument("--file", type=str, help="Specific transcript file to analyze")
    args = parser.parse_args()

    transcripts = load_transcripts(args.file)
    if not transcripts:
        print("No transcripts found. Run some calls first!")
        return

    print(f"📋 Analyzing {len(transcripts)} transcript(s)...")
    report = analyze_transcripts(transcripts)

    # Save report
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"bug_report_{ts}.md"
    with open(report_file, "w") as f:
        f.write(report)

    print(f"\n✅ Bug report saved: {report_file}")
    print("\n" + "=" * 60)
    print(report)


if __name__ == "__main__":
    main()
