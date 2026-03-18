# DocAnalystAgent

AI-powered document analysis agent. Upload any document and get instant Chinese translation, executive summary, objective suggestions, probing questions — all anchored to exact page, section, and line references — plus an interactive chat.

## Features

- **Multi-format upload** — PDF, DOCX, PPTX, XLSX, TXT, CSV, MD
- **Chinese translation** — full document translated to Simplified Chinese, page structure preserved
- **Executive summary** — key points, topics, tone, and completeness assessment in English and Chinese
- **Objective suggestions** — 8 actionable improvements tagged by severity (high/medium/low) and type (clarity, accuracy, logic, structure, evidence, tone, completeness), each linked to an exact Page · Section · Line
- **Probing questions** — 8 critical questions by category (assumption, evidence, risk, feasibility, methodology, etc.), location-anchored with an "Ask in Chat ↗" shortcut that opens the chat pre-filled
- **Floating chat** — 💬 button in the bottom-right corner opens a popup for interactive Q&A with full document context; responds in English or Chinese; red dot badge when a reply arrives while closed
- **Dark-theme UI** — single-page app with filters, expandable cards, and location navigation

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + Uvicorn |
| AI | Anthropic Claude claude-opus-4-6 |
| Document parsing | PyMuPDF (PDF), python-docx (DOCX), python-pptx (PPTX), openpyxl (XLSX) |
| Frontend | Vanilla JS + Jinja2 templates |

## Setup

**1. Clone the repo**
```bash
git clone https://github.com/garyhe231/DocAnalystAgent.git
cd DocAnalystAgent
```

**2. Install dependencies**
```bash
pip3 install -r requirements.txt
```

**3. Set your API key**

Direct Anthropic API:
```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

Or via AWS Bedrock (no API key needed if `AWS_PROFILE` / `AWS_REGION` are set):
```bash
export AWS_PROFILE=your-profile
export AWS_REGION=us-east-1
```

**4. Run**
```bash
python3 run.py
```

Open http://localhost:8012 in your browser.

## Usage

1. **Upload** a document by clicking the upload zone or dragging a file onto it
2. Click **Analyze Document** to generate summary, suggestions, and questions (runs in parallel)
3. Click **Translate to Chinese** for a full Simplified Chinese translation
4. Browse results in the **Summary**, **Suggestions**, and **Questions** tabs
5. Use the filter bar to narrow by severity, type, or category
6. Click any **Page · Section · Line** chip to jump to that location in the translation
7. Click the **💬 button** (bottom-right) to open the chat popup and ask follow-up questions in English or Chinese
8. Use **Ask in Chat ↗** on any question card to send it directly to the chat

## Project Structure

```
DocAnalystAgent/
├── run.py                        # Entry point (port 8012)
├── requirements.txt
├── app/
│   ├── main.py                   # FastAPI routes and session management
│   ├── services/
│   │   ├── extractor.py          # Document parser → structured pages with sections and lines
│   │   └── analyst.py            # Claude-powered analysis: translate, summarize, suggest, question, chat
│   ├── static/
│   │   ├── css/style.css
│   │   └── js/app.js
│   └── templates/index.html
└── data/                         # Runtime only (gitignored)
    ├── uploads/
    └── sessions/
```

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/upload` | Upload a document, returns `session_id` |
| `POST` | `/api/analyze/{session_id}` | Run full analysis (summary + suggestions + questions) |
| `POST` | `/api/translate/{session_id}` | Translate document to Chinese |
| `POST` | `/api/chat/{session_id}` | Streaming chat (SSE) |
| `GET` | `/api/session/{session_id}` | Retrieve session results |
| `DELETE` | `/api/session/{session_id}` | Delete session and uploaded file |
