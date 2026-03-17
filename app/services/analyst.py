"""
AI analyst service — translation, summary, suggestions, questions, and chat.
All analysis is anchored to page + section + line references.
Supports both direct Anthropic API (ANTHROPIC_API_KEY) and AWS Bedrock (AWS_PROFILE/AWS_REGION).
"""
import os
import json
import anthropic
from typing import List, Dict, Any, Optional, AsyncIterator
from pathlib import Path

from .extractor import full_text

# Load .env if present
_env_path = Path(__file__).parent.parent.parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

# Use Bedrock if no direct API key is set
if os.environ.get("ANTHROPIC_API_KEY"):
    client = anthropic.Anthropic()
    MODEL = os.environ.get("ANTHROPIC_DEFAULT_OPUS_MODEL", "claude-opus-4-6")
else:
    client = anthropic.AnthropicBedrock()
    MODEL = os.environ.get(
        "ANTHROPIC_DEFAULT_OPUS_MODEL",
        "anthropic.claude-opus-4-5",
    )

SYSTEM_PROMPT = """You are a precise, objective document analyst. You:
- Read documents carefully and provide structured, actionable analysis
- Always cite exact locations: Page X, Section "Y", Line Z
- Are objective and constructive — point out both strengths and weaknesses
- Ask probing questions that expose gaps, assumptions, or areas needing clarification
- Respond in the same language as requested (Chinese or English)
"""


def _parse_json(text: str) -> Any:
    """
    Extract and parse JSON from a model response.
    Handles code fences, unicode smart-quotes, and unescaped inner double-quotes
    that models sometimes embed inside JSON string values.
    """
    import re

    def _sanitize(s: str) -> str:
        """Normalize known non-JSON characters."""
        s = s.replace('\u2018', "'").replace('\u2019', "'")   # curly single quotes
        s = s.replace('\u2013', '-').replace('\u2014', '-')    # en/em dashes
        s = s.replace('\u201c', '\\"').replace('\u201d', '\\"')  # curly double quotes → escaped
        s = s.replace('\uff02', '\\"')                           # fullwidth quotation mark
        return s

    def _fix_unescaped_quotes(s: str) -> str:
        """
        Walk the JSON string character-by-character.
        When inside a JSON string value, replace bare " with \".
        This fixes cases where the model wrote "平均"运输时间" instead of "平均\"运输时间\"".
        """
        result = []
        in_string = False
        prev_backslash = False
        i = 0
        while i < len(s):
            ch = s[i]
            if prev_backslash:
                result.append(ch)
                prev_backslash = False
                i += 1
                continue
            if ch == '\\':
                result.append(ch)
                prev_backslash = True
                i += 1
                continue
            if ch == '"':
                if not in_string:
                    in_string = True
                    result.append(ch)
                else:
                    # Peek ahead: is the next non-whitespace char a JSON structural char?
                    j = i + 1
                    while j < len(s) and s[j] in ' \t\n\r':
                        j += 1
                    next_ch = s[j] if j < len(s) else ''
                    if next_ch in (',', '}', ']', ':'):
                        # This is a closing quote
                        in_string = False
                        result.append(ch)
                    else:
                        # Unescaped inner quote — escape it
                        result.append('\\"')
                i += 1
                continue
            result.append(ch)
            i += 1
        return ''.join(result)

    def _try_parse(s: str) -> Any:
        s = _sanitize(s)
        # First attempt: direct parse
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            pass
        # Second attempt: fix unescaped inner quotes
        try:
            return json.loads(_fix_unescaped_quotes(s))
        except json.JSONDecodeError:
            pass
        raise ValueError("unparseable")

    candidates = []

    # Extract from code fences
    if "```" in text:
        parts = text.split("```")
        for part in parts[1::2]:
            cleaned = part.strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
            candidates.append(cleaned)

    # Outermost bracket extraction
    for start_char, end_char in [('[', ']'), ('{', '}')]:
        start = text.find(start_char)
        end = text.rfind(end_char)
        if start != -1 and end != -1 and end > start:
            candidates.append(text[start:end + 1])

    # Raw text
    candidates.append(text.strip())

    for candidate in candidates:
        try:
            return _try_parse(candidate)
        except (ValueError, Exception):
            pass

    raise ValueError(f"Could not parse JSON from model response: {text[:300]}")


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
    return _parse_json(response.content[0].text)


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

Provide exactly 8 suggestions covering different parts of the document. Keep each field concise (under 120 chars)."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_json(response.content[0].text)


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

Generate exactly 8 questions that a critical reviewer or decision-maker would ask. Keep each field concise (under 120 chars)."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_json(response.content[0].text)


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
