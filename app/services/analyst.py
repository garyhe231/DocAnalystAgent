"""
AI analyst service — translation, summary, suggestions, questions, and chat.
All analysis is anchored to page + section + line references.
"""
import json
import anthropic
from typing import List, Dict, Any, Optional, AsyncIterator

from .extractor import full_text

client = anthropic.Anthropic()
MODEL = "claude-opus-4-6"

SYSTEM_PROMPT = """You are a precise, objective document analyst. You:
- Read documents carefully and provide structured, actionable analysis
- Always cite exact locations: Page X, Section "Y", Line Z
- Are objective and constructive — point out both strengths and weaknesses
- Ask probing questions that expose gaps, assumptions, or areas needing clarification
- Respond in the same language as requested (Chinese or English)
"""


def _doc_context(doc_data: Dict[str, Any]) -> str:
    """Build a structured context string from the document."""
    parts = []
    for page in doc_data["pages"]:
        page_text = f"\n=== PAGE {page['page']} ===\n"
        for sec in page.get("sections", []):
            page_text += f"\n[Section: {sec['heading']}]\n"
            for ln in sec.get("lines", []):
                page_text += f"  Line {ln['line']}: {ln['text']}\n"
        parts.append(page_text)
    return "".join(parts)


def translate_to_chinese(doc_data: Dict[str, Any]) -> str:
    """Translate full document to Chinese, preserving page structure."""
    context = _doc_context(doc_data)
    total = doc_data["total_pages"]

    prompt = f"""Translate the following document to Chinese (Simplified).
Preserve the page structure markers (=== PAGE X ===) and section headings.
Keep all numbers, names, and technical terms accurate.

Document ({total} pages):
{context}

Provide the complete Chinese translation, keeping the same structural markers."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def summarize(doc_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a structured summary with key points."""
    context = _doc_context(doc_data)

    prompt = f"""Analyze this document and provide a structured summary in JSON format.

Document:
{context}

Return ONLY valid JSON with this structure:
{{
  "title": "inferred document title",
  "document_type": "type of document (report/contract/proposal/etc)",
  "language": "original language",
  "total_pages": {doc_data["total_pages"]},
  "executive_summary": "2-3 sentence overview in English",
  "executive_summary_zh": "2-3 sentence overview in Chinese",
  "key_points": [
    {{"point": "key finding or point", "page": 1, "section": "section name"}}
  ],
  "main_topics": ["topic1", "topic2"],
  "tone": "formal/informal/technical/etc",
  "completeness": "assessment of document completeness"
}}"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=3000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text
    # Extract JSON even if wrapped in code fences
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def generate_suggestions(doc_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate objective suggestions anchored to specific locations."""
    context = _doc_context(doc_data)

    prompt = f"""Review this document objectively and generate specific, actionable improvement suggestions.
For each suggestion, pinpoint the exact location (page, section, approximate line).

Document:
{context}

Return ONLY valid JSON — a list of suggestion objects:
[
  {{
    "id": 1,
    "type": "clarity|accuracy|completeness|structure|logic|tone|evidence",
    "severity": "high|medium|low",
    "page": 1,
    "section": "section heading",
    "line": 10,
    "original_text": "the specific text being addressed (or empty if structural)",
    "suggestion": "clear, actionable suggestion in English",
    "suggestion_zh": "same suggestion in Chinese",
    "rationale": "why this change would improve the document"
  }}
]

Provide 8-15 substantive suggestions covering different parts of the document."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def generate_questions(doc_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate probing questions about the document."""
    context = _doc_context(doc_data)

    prompt = f"""As an objective reviewer, generate probing questions about this document.
Questions should expose gaps, untested assumptions, missing evidence, or areas needing clarification.
Anchor each question to the specific location that prompted it.

Document:
{context}

Return ONLY valid JSON — a list of question objects:
[
  {{
    "id": 1,
    "category": "assumption|evidence|completeness|consistency|feasibility|stakeholder|risk|methodology",
    "page": 1,
    "section": "section heading",
    "line": 10,
    "question": "the probing question in English",
    "question_zh": "same question in Chinese",
    "importance": "high|medium|low",
    "context": "brief explanation of why this question matters"
  }}
]

Generate 10-15 questions that a critical reviewer or decision-maker would ask."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


async def chat_stream(
    doc_data: Dict[str, Any],
    history: List[Dict[str, str]],
    user_message: str,
) -> AsyncIterator[str]:
    """Streaming chat about the document."""
    context = _doc_context(doc_data)
    system = SYSTEM_PROMPT + f"""

You have access to the following document for reference:
{context}

When answering questions:
- Cite specific pages and sections when relevant
- Be concise but thorough
- If asked in Chinese, respond in Chinese; if in English, respond in English
- You may be asked about the document content, the analysis results, or general questions
"""

    messages = history[-10:] + [{"role": "user", "content": user_message}]

    with client.messages.stream(
        model=MODEL,
        max_tokens=2000,
        system=system,
        messages=messages,
    ) as stream:
        for text in stream.text_stream:
            yield text
