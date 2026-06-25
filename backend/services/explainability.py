import os
from pathlib import Path
from groq import Groq
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
load_dotenv(env_path, encoding="utf-8")

api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise RuntimeError(
        f"GROQ_API_KEY not found. Looked for .env at: {env_path}\n"
        "Make sure .env exists in your Legal-Ai-Platform root folder."
    )

client = Groq(api_key=api_key)


def generate_explanation(risk_analysis: dict) -> dict:
    """
    Uses Groq (free) to generate plain-English clause explanations.
    Model: llama-3.1-8b-instant — fast, free, 14400 requests/day
    """
    clause_text = risk_analysis.get("clause_text", "")
    clause_type = risk_analysis.get("type", "Unknown")
    risk_level  = risk_analysis.get("risk_level", "LOW")
    risk_reason = risk_analysis.get("risk_reason", "")

    prompt = f"""You are a legal analyst reviewing an NDA (Non-Disclosure Agreement).

Clause type: {clause_type}
Risk level: {risk_level}
Risk reason: {risk_reason}

Clause text:
\"\"\"{clause_text[:400]}\"\"\"

Provide a plain-English explanation of exactly 3 bullet points (one sentence per bullet):
- Meaning: What this clause means in simple, practical terms.
- Risk Justification: Why this is flagged as a {risk_level} risk.
- Watch Out: One specific catch or detail the signing party must look out for.

Be concise and practical. No legal jargon."""

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": "You are a concise legal analyst. Always respond in 2-3 plain English sentences."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=200,
            temperature=0.3
        )
        explanation = response.choices[0].message.content.strip()

    except Exception as e:
        print(f"[explainability] Groq API call failed: {e}")
        explanation = (
            f"Clause flagged as {risk_level} RISK.\n"
            f"Reason: {risk_reason}"
        )

    risk_analysis["explanation"] = explanation
    return risk_analysis