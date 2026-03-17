import os
import uuid
import json
import asyncio
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from .services import extractor, analyst

BASE_DIR = Path(__file__).parent.parent
UPLOAD_DIR = BASE_DIR / "data" / "uploads"
SESSION_DIR = BASE_DIR / "data" / "sessions"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
SESSION_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="DocAnalystAgent")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))

# In-memory session store: session_id -> {doc_data, filename, analysis}
sessions: dict = {}


def _save_session(session_id: str):
    path = SESSION_DIR / f"{session_id}.json"
    data = sessions.get(session_id, {})
    # Don't persist doc_data (large), only analysis results + history
    save_data = {
        "filename": data.get("filename"),
        "summary": data.get("summary"),
        "suggestions": data.get("suggestions"),
        "questions": data.get("questions"),
        "translation_snippet": (data.get("translation") or "")[:500],
        "history": data.get("history", []),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)


def _load_sessions():
    for path in SESSION_DIR.glob("*.json"):
        sid = path.stem
        with open(path, "r", encoding="utf-8") as f:
            sessions[sid] = json.load(f)


_load_sessions()


# ──────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    suffix = Path(file.filename).suffix.lower()
    allowed = {".pdf", ".docx", ".pptx", ".xlsx", ".xls", ".txt", ".md", ".csv"}
    if suffix not in allowed:
        raise HTTPException(400, f"Unsupported file type: {suffix}. Allowed: {', '.join(allowed)}")

    session_id = str(uuid.uuid4())[:8]
    dest = UPLOAD_DIR / f"{session_id}_{file.filename}"
    content = await file.read()
    with open(dest, "wb") as f:
        f.write(content)

    try:
        doc_data = extractor.extract(str(dest), file.filename)
    except Exception as e:
        dest.unlink(missing_ok=True)
        raise HTTPException(500, f"Extraction failed: {e}")

    sessions[session_id] = {
        "filename": file.filename,
        "file_path": str(dest),
        "doc_data": doc_data,
        "history": [],
    }
    return {
        "session_id": session_id,
        "filename": file.filename,
        "total_pages": doc_data["total_pages"],
        "preview": extractor.full_text(doc_data)[:800],
    }


@app.post("/api/analyze/{session_id}")
async def analyze(session_id: str):
    if session_id not in sessions or "doc_data" not in sessions[session_id]:
        raise HTTPException(404, "Session not found or document not loaded")

    doc_data = sessions[session_id]["doc_data"]

    # Run all three analyses (summary, suggestions, questions) in parallel threads
    loop = asyncio.get_event_loop()
    summary_task = loop.run_in_executor(None, analyst.summarize, doc_data)
    suggestions_task = loop.run_in_executor(None, analyst.generate_suggestions, doc_data)
    questions_task = loop.run_in_executor(None, analyst.generate_questions, doc_data)

    summary, suggestions, questions = await asyncio.gather(
        summary_task, suggestions_task, questions_task
    )

    sessions[session_id]["summary"] = summary
    sessions[session_id]["suggestions"] = suggestions
    sessions[session_id]["questions"] = questions
    _save_session(session_id)

    return {"summary": summary, "suggestions": suggestions, "questions": questions}


@app.post("/api/translate/{session_id}")
async def translate(session_id: str):
    if session_id not in sessions or "doc_data" not in sessions[session_id]:
        raise HTTPException(404, "Session not found or document not loaded")

    doc_data = sessions[session_id]["doc_data"]
    loop = asyncio.get_event_loop()
    translation = await loop.run_in_executor(None, analyst.translate_to_chinese, doc_data)
    sessions[session_id]["translation"] = translation
    _save_session(session_id)
    return {"translation": translation}


class ChatMessage(BaseModel):
    message: str


@app.post("/api/chat/{session_id}")
async def chat(session_id: str, body: ChatMessage):
    if session_id not in sessions or "doc_data" not in sessions[session_id]:
        raise HTTPException(404, "Session not found or document not loaded")

    doc_data = sessions[session_id]["doc_data"]
    history = sessions[session_id].get("history", [])

    async def event_stream():
        full_response = ""
        async for chunk in analyst.chat_stream(doc_data, history, body.message):
            full_response += chunk
            yield f"data: {json.dumps({'text': chunk})}\n\n"

        # Save to history
        history.append({"role": "user", "content": body.message})
        history.append({"role": "assistant", "content": full_response})
        sessions[session_id]["history"] = history[-20:]
        _save_session(session_id)
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    if session_id not in sessions:
        raise HTTPException(404, "Session not found")
    s = sessions[session_id]
    return {
        "session_id": session_id,
        "filename": s.get("filename"),
        "total_pages": s.get("doc_data", {}).get("total_pages") if "doc_data" in s else None,
        "has_analysis": "summary" in s,
        "has_translation": "translation" in s,
        "summary": s.get("summary"),
        "suggestions": s.get("suggestions"),
        "questions": s.get("questions"),
        "translation": s.get("translation"),
        "history": s.get("history", []),
    }


@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str):
    if session_id in sessions:
        s = sessions.pop(session_id)
        fp = s.get("file_path")
        if fp:
            Path(fp).unlink(missing_ok=True)
        (SESSION_DIR / f"{session_id}.json").unlink(missing_ok=True)
    return {"ok": True}
