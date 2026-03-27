# NL2SQL Clinic Chatbot

An AI-powered Natural Language to SQL system built with **Vanna 2.0** and **FastAPI**.  
Ask questions about a clinic database in plain English — the system generates and runs SQL automatically.

---

## Tech Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.10+ | Backend language |
| Vanna | 2.0.x | AI Agent for NL→SQL |
| FastAPI | Latest | REST API framework |
| SQLite | Built-in | Database |
| Google Gemini | 2.5-flash | LLM (default, free) |
| Plotly | Latest | Chart generation |

---

## Project Structure

```
nl2sql_project/
├── setup_database.py   # Creates clinic.db with schema + dummy data
├── vanna_setup.py      # Vanna 2.0 Agent initialization
├── seed_memory.py      # Pre-seeds agent with 15 Q&A pairs
├── sql_validator.py    # SQL safety validation
├── main.py             # FastAPI application
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variable template
├── RESULTS.md          # 20-question test results
└── clinic.db           # Generated database (after running setup)
```

---

## Setup Instructions

### 1. Clone / download the project

```bash
git clone <your-repo-url>
cd nl2sql_project
```

### 2. Create a virtual environment

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure your API key

Copy the example env file and fill in your key:

```bash
cp .env.example .env
```

Edit `.env`:

```
# For Google Gemini (default — free key from https://aistudio.google.com/apikey)
LLM_PROVIDER=gemini
GOOGLE_API_KEY=your-key-here

# OR for Groq (free tier from https://console.groq.com)
# LLM_PROVIDER=groq
# GROQ_API_KEY=your-key-here

# OR for Ollama (fully local, no API key)
# LLM_PROVIDER=ollama
# First run: ollama pull llama3
```

> **Never commit your `.env` file.** It is in `.gitignore` by default.

### 5. Create the database

```bash
python setup_database.py
```

Expected output:
```
✅ Database created: clinic.db
   Created 200 patients
   Created 15 doctors
   Created 500 appointments
   Created 350 treatments
   Created 300 invoices
```

### 6. Seed agent memory

```bash
python seed_memory.py
```

Expected output:
```
Building agent …
✅ Vanna 2.0 Agent built successfully  (provider=gemini)
Seeding 15 Q&A pairs into DemoAgentMemory …
  [01] ✓  How many patients do we have?
  ...
✅ Seeding complete. Memory now has 15 entries.
```

### 7. Start the API server

```bash
uvicorn main:app --port 8000 --reload
```

The API is now live at `http://localhost:8000`.  
Interactive docs: `http://localhost:8000/docs`

---

## One-line startup (after initial setup)

```bash
pip install -r requirements.txt && python setup_database.py && python seed_memory.py && uvicorn main:app --port 8000
```

---

## API Documentation

### POST `/chat`

Ask a natural-language question.

**Request:**
```json
{
  "question": "Show me the top 5 patients by total spending"
}
```

**Response:**
```json
{
  "message": "Here are the top 5 patients by total spending ...",
  "sql_query": "SELECT p.first_name, p.last_name, SUM(i.total_amount) AS total_spending FROM invoices i JOIN patients p ON p.id = i.patient_id GROUP BY p.id ORDER BY total_spending DESC LIMIT 5;",
  "columns": ["first_name", "last_name", "total_spending"],
  "rows": [["John", "Smith", 4500], ["Jane", "Doe", 3200]],
  "row_count": 5,
  "chart": { "data": [...], "layout": {...} },
  "chart_type": "bar",
  "cached": false
}
```

**cURL example:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "How many patients do we have?"}'
```

---

### GET `/health`

Check that the database is connected and how many memory items are loaded.

**Response:**
```json
{
  "status": "ok",
  "database": "connected",
  "agent_memory_items": 15,
  "timestamp": "2025-01-01T12:00:00Z"
}
```

---

## Architecture Overview

```
User Question (English)
        │
        ▼
  FastAPI /chat endpoint
        │
        ├─► Input validation (length, blank check)
        │
        ▼
  Rate Limiter (20 req / 60 s per IP)
        │
        ▼
  Cache Check (in-memory, per question)
        │
        ▼
  Vanna 2.0 Agent
  ┌─────────────────────────────────┐
  │  GeminiLlmService               │
  │  DemoAgentMemory (15 Q&A pairs) │
  │  RunSqlTool                     │
  │  VisualizeDataTool              │
  └─────────────────────────────────┘
        │
        ▼
  SQL Validator (SELECT-only, no dangerous keywords)
        │
        ▼
  SQLite Runner (clinic.db)
        │
        ▼
  Results + Plotly Chart
        │
        ▼
  JSON Response to User
```

---

## Bonus Features Implemented

- ✅ **Chart Generation** — Plotly bar/line charts auto-selected based on result shape
- ✅ **Input Validation** — min/max length, blank-check via Pydantic
- ✅ **Query Caching** — identical questions served from in-memory cache
- ✅ **Rate Limiting** — 20 requests / 60 seconds per IP (configurable via `.env`)
- ✅ **Structured Logging** — timestamped logs for all pipeline steps

---

## LLM Provider

This project uses **Google Gemini (gemini-2.5-flash)** by default.  
To switch, set `LLM_PROVIDER` in your `.env` file to `groq` or `ollama`.

---

## Resources

- [Vanna AI Documentation](https://vanna.ai/docs)
- [Vanna 2.0 Quickstart](https://vanna.ai/docs/tutorials/quickstart-5min)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [Google AI Studio (free Gemini key)](https://aistudio.google.com/apikey)
- [Groq Console (free tier)](https://console.groq.com)
- [Ollama (local LLM)](https://ollama.com)
