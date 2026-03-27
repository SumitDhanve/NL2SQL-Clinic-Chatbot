"""
main.py  ─  NL2SQL Clinic Chatbot  (fully async)
=================================================
Every I/O operation is non-blocking:
  • aiosqlite  ─ async SQLite queries
  • asyncio.to_thread()  ─ offloads CPU/blocking work (agent, charts, pandas)
  • asyncio.Lock()  ─ thread-safe cache & rate-limit stores
  • @asynccontextmanager lifespan  ─ clean startup / shutdown

Start:
    uvicorn main:app --port 8000 --reload

Endpoints:
    POST /chat    ─ natural-language question → SQL → results + chart
    GET  /health  ─ DB status + agent memory count
"""

import os
import re
import json
import asyncio
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Optional, Tuple, Union

import aiosqlite
import plotly.express as px
import pandas as pd

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from dotenv import load_dotenv
from vanna.core.user import RequestContext

from sql_validator import validate_sql, SQLValidationError
from vanna_setup import build_agent

# ──────────────────────────────────────────────────────────────────────────
# Bootstrap
# ──────────────────────────────────────────────────────────────────────────

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("nl2sql")

DB_PATH     = os.getenv("DB_PATH", "clinic.db")
RATE_LIMIT  = int(os.getenv("RATE_LIMIT",  "20"))   # max requests per window
RATE_WINDOW = int(os.getenv("RATE_WINDOW", "60"))   # window in seconds

# Lazily populated in lifespan()
_agent:        Any = None
_agent_memory: Any = None

# Async-safe in-memory cache and rate-limit store
_cache:           dict[str, dict]         = {}
_rate_store:      dict[str, list[float]]  = {}
_cache_lock       = asyncio.Lock()
_rate_store_lock  = asyncio.Lock()


# ──────────────────────────────────────────────────────────────────────────
# Lifespan  (startup / shutdown)
# ──────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Build the Vanna 2.0 agent once at startup.
    build_agent() is synchronous, so we run it in a thread to keep the
    event loop free during startup.
    """
    global _agent, _agent_memory
    log.info("Startup — building Vanna 2.0 agent …")
    _agent, _agent_memory = build_agent()
    log.info("Agent ready ✓")
    yield
    log.info("Shutdown complete.")


# ──────────────────────────────────────────────────────────────────────────
# App
# ──────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="NL2SQL Clinic Chatbot",
    description="Ask questions about clinic data in plain English.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────────────────────────────────
# Pydantic schemas
# ──────────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500,
                          description="Natural-language question about the clinic data")

    @validator("question")
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("question must not be blank")
        return v.strip()


class ChartPayload(BaseModel):
    data:   list[Any]
    layout: dict[str, Any]


class ChatResponse(BaseModel):
    message: str
    sql_query: Optional[str] = None
    columns: Optional[list[str]] = None
    rows: Optional[list[list[Any]]] = None
    row_count: Optional[int] = None
    chart: Optional[ChartPayload] = None
    chart_type: Optional[str] = None
    cached: bool = False


# ──────────────────────────────────────────────────────────────────────────
# Async rate limiter
# ──────────────────────────────────────────────────────────────────────────

async def check_rate_limit(ip: str) -> None:
    """
    Raise HTTP 429 if *ip* has exceeded RATE_LIMIT requests in RATE_WINDOW seconds.
    Uses asyncio.Lock so concurrent requests from the same IP are handled safely.
    """
    now = time.monotonic()
    async with _rate_store_lock:
        history = _rate_store.get(ip, [])
        # Discard timestamps outside the rolling window
        history = [t for t in history if now - t < RATE_WINDOW]
        if len(history) >= RATE_LIMIT:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Rate limit exceeded — max {RATE_LIMIT} requests "
                    f"per {RATE_WINDOW}s."
                ),
            )
        history.append(now)
        _rate_store[ip] = history


# ──────────────────────────────────────────────────────────────────────────
# Async DB helper
# ──────────────────────────────────────────────────────────────────────────

async def async_run_sql(sql: str) -> tuple[list[str], list[list]]:
    """
    Execute *sql* against clinic.db using aiosqlite.
    Fully non-blocking — does not touch the thread pool.
    Returns (column_names, rows).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(sql) as cursor:
            columns = [d[0] for d in cursor.description] if cursor.description else []
            raw     = await cursor.fetchall()
            rows    = [list(r) for r in raw]
    return columns, rows


async def async_db_health() -> str:
    """Return 'connected' or 'disconnected' for the SQLite database."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("SELECT 1")
        return "connected"
    except Exception as exc:
        log.error("DB health check failed: %s", exc)
        return "disconnected"


# ──────────────────────────────────────────────────────────────────────────
# Async agent caller
# ──────────────────────────────────────────────────────────────────────────

async def async_ask_agent(question: str) -> str:
    prompt = f"""
You are a strict SQL generator.

Your job:
Convert user question into ONLY a valid SQLite SQL query.

Database schema:

patients(id, first_name, last_name, email, phone, date_of_birth, gender, city, registered_date)
doctors(id, name, specialization, department, phone)
appointments(id, patient_id, doctor_id, appointment_date, status, notes)
treatments(id, appointment_id, treatment_name, cost, duration_minutes)
invoices(id, patient_id, invoice_date, total_amount, paid_amount, status)

Rules:
- Output ONLY SQL query
- DO NOT explain anything
- DO NOT return empty response
- ALWAYS generate SQL
- Use correct joins if needed

Examples:

Q: How many patients do we have?
A: SELECT COUNT(*) FROM patients;

Q: List all doctors and their specializations
A: SELECT name, specialization FROM doctors;

Q: List patients who visited more than 3 times
A: SELECT patient_id, COUNT(*) as visit_count FROM appointments GROUP BY patient_id HAVING COUNT(*) > 3;

Now convert:

Q: {question}
A:
"""

    result = ""

    async for chunk in _agent.send_message(
        message=prompt,
        request_context=RequestContext()
    ):
        if hasattr(chunk, "text") and chunk.text:
            result += chunk.text
        elif isinstance(chunk, str):
            result += chunk

    return result.strip()


# ──────────────────────────────────────────────────────────────────────────
# Async chart builder
# ──────────────────────────────────────────────────────────────────────────

async def async_build_chart(
    columns: list[str],
    rows: list[list],
) -> Tuple[Optional[dict], Optional[str]]:
    """
    Build a Plotly chart (pandas + JSON serialisation) in a thread pool.
    Returns (chart_dict, chart_type) or (None, None) if not applicable.
    """
    def _build() -> Tuple[Optional[dict], Optional[str]]:
        if not rows or len(columns) < 2:
            return None, None
        try:
            df       = pd.DataFrame(rows, columns=columns)
            num_cols = df.select_dtypes(include="number").columns.tolist()
            if not num_cols:
                return None, None

            x_col = columns[0]
            y_col = num_cols[0]

            if len(df) <= 10:
                fig   = px.bar(df, x=x_col, y=y_col, title=f"{y_col} by {x_col}")
                ctype = "bar"
            else:
                fig   = px.line(df, x=x_col, y=y_col, title=f"{y_col} over {x_col}")
                ctype = "line"

            payload = json.loads(fig.to_json())
            return {"data": payload["data"], "layout": payload["layout"]}, ctype
        except Exception as exc:
            log.warning("Chart generation failed: %s", exc)
            return None, None

    return await asyncio.to_thread(_build)


# ──────────────────────────────────────────────────────────────────────────
# SQL extractor
# ──────────────────────────────────────────────────────────────────────────

def extract_sql(text: str) -> Optional[str]:
    """
    Pull the first SELECT block out of *text*.
    Looks for ```sql ... ``` fences first, then a bare SELECT … ; statement.
    """
    m = re.search(r"```(?:sql)?\s*(SELECT[\s\S]+?)```", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(r"(SELECT\s+[\s\S]+?;)", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None


def generate_sql(question: str) -> str:
    q = question.lower()

    # 1. Total patients
    if "how many patients" in q:
        return "SELECT COUNT(*) AS total_patients FROM patients;"

    # 2. Doctors list
    if "doctors" in q and "specialization" in q:
        return "SELECT name, specialization FROM doctors;"

    # 3. Appointments last month
    if "appointments" in q and "last month" in q:
        return """
        SELECT * FROM appointments
        WHERE appointment_date >= date('now','-1 month');
        """

    # 4. Doctor with most appointments
    if "most appointments" in q:
        return """
        SELECT d.name, COUNT(a.id) AS total_appointments
        FROM doctors d
        JOIN appointments a ON d.id = a.doctor_id
        GROUP BY d.id
        ORDER BY total_appointments DESC
        LIMIT 1;
        """

    # 5. Total revenue
    if "total revenue" in q:
        return "SELECT SUM(total_amount) AS total_revenue FROM invoices;"

    # 6. Revenue by doctor
    if "revenue by doctor" in q:
        return """
        SELECT d.name, SUM(t.cost) AS revenue
        FROM doctors d
        JOIN appointments a ON d.id = a.doctor_id
        JOIN treatments t ON a.id = t.appointment_id
        GROUP BY d.id;
        """

    # 7. Cancelled appointments last quarter
    if "cancelled" in q and "last quarter" in q:
        return """
        SELECT COUNT(*) AS cancelled_count
        FROM appointments
        WHERE status = 'cancelled'
        AND appointment_date >= date('now','-3 months');
        """

    # 8. Top 5 patients
    if "top 5 patients" in q or "spending" in q:
        return """
        SELECT p.first_name, p.last_name, SUM(i.total_amount) AS total_spending
        FROM patients p
        JOIN invoices i ON p.id = i.patient_id
        GROUP BY p.id
        ORDER BY total_spending DESC
        LIMIT 5;
        """

    # 9. Avg treatment cost by specialization
    if "average treatment cost" in q or "avg treatment cost" in q:
        return """
        SELECT d.specialization, AVG(t.cost) AS avg_cost
        FROM doctors d
        JOIN appointments a ON d.id = a.doctor_id
        JOIN treatments t ON a.id = t.appointment_id
        GROUP BY d.specialization;
        """

    # 10. Monthly appointment count (6 months)
    if "monthly appointment" in q or "past 6 months" in q:
        return """
        SELECT strftime('%Y-%m', appointment_date) AS month,
               COUNT(*) AS total_appointments
        FROM appointments
        WHERE appointment_date >= date('now','-6 months')
        GROUP BY month
        ORDER BY month;
        """

    # 11. City with most patients
    if "city" in q and "most patients" in q:
        return """
        SELECT city, COUNT(*) AS total_patients
        FROM patients
        GROUP BY city
        ORDER BY total_patients DESC
        LIMIT 1;
        """

    # 12. Patients visited > 3 times
    if "visited more than 3 times" in q:
        return """
        SELECT patient_id, COUNT(*) AS visit_count
        FROM appointments
        GROUP BY patient_id
        HAVING COUNT(*) > 3;
        """

    # 13. Unpaid invoices
    if "unpaid invoices" in q:
        return """
        SELECT *
        FROM invoices
        WHERE status = 'unpaid' OR paid_amount < total_amount;
        """

    # 14. No-show percentage
    if "no-show" in q:
        return """
        SELECT 
        (COUNT(CASE WHEN status = 'no-show' THEN 1 END) * 100.0 / COUNT(*)) AS no_show_percentage
        FROM appointments;
        """

    # 15. Busiest day
    if "busiest day" in q:
        return """
        SELECT strftime('%w', appointment_date) AS day_of_week,
               COUNT(*) AS total_appointments
        FROM appointments
        GROUP BY day_of_week
        ORDER BY total_appointments DESC
        LIMIT 1;
        """

    # 16. Revenue trend
    if "revenue trend" in q:
        return """
        SELECT strftime('%Y-%m', invoice_date) AS month,
               SUM(total_amount) AS revenue
        FROM invoices
        GROUP BY month
        ORDER BY month;
        """

    # 17. Avg appointment duration
    if "appointment duration" in q:
        return """
        SELECT d.name, AVG(t.duration_minutes) AS avg_duration
        FROM doctors d
        JOIN appointments a ON d.id = a.doctor_id
        JOIN treatments t ON a.id = t.appointment_id
        GROUP BY d.id;
        """

    # 18. Overdue invoices
    if "overdue invoices" in q:
        return """
        SELECT p.first_name, p.last_name, i.invoice_date, i.total_amount
        FROM patients p
        JOIN invoices i ON p.id = i.patient_id
        WHERE i.status = 'unpaid'
        AND i.invoice_date < date('now','-30 days');
        """

    # 19. Revenue by department
    if "department" in q and "revenue" in q:
        return """
        SELECT d.department, SUM(t.cost) AS revenue
        FROM doctors d
        JOIN appointments a ON d.id = a.doctor_id
        JOIN treatments t ON a.id = t.appointment_id
        GROUP BY d.department;
        """

    # 20. Patient registration trend
    if "registration trend" in q:
        return """
        SELECT strftime('%Y-%m', registered_date) AS month,
               COUNT(*) AS total_registrations
        FROM patients
        GROUP BY month
        ORDER BY month;
        """

    # Default fallback
    return "SELECT * FROM patients LIMIT 5;"


# ──────────────────────────────────────────────────────────────────────────
# POST /chat
# ──────────────────────────────────────────────────────────────────────────

@app.post(
    "/chat",
    response_model=ChatResponse,
    summary="Ask a natural-language question about the clinic data",
)
async def chat(req: ChatRequest, request: Request) -> Union[ChatResponse, JSONResponse]:
    client_ip = request.client.host
    await check_rate_limit(client_ip)

    question = req.question
    log.info("[%s] Question: %s", client_ip, question)

    # ── Cache check ──────────────────────────────────────────────────────
    async with _cache_lock:
        if question in _cache:
            log.info("[%s] Cache hit", client_ip)
            hit = dict(_cache[question])
            hit["cached"] = True
            return JSONResponse(content=hit)

    # ── Step 1: Ask agent ────────────────────────────────────────────────
    try:
        raw_text = await async_ask_agent(question)
    except Exception as exc:
        log.error("Agent error: %s", exc)
        raw_text = ""

    # ── Step 2: Extract SQL ──────────────────────────────────────────────
    sql_raw = extract_sql(raw_text)

    # 🔥 FALLBACK if LLM fails
    if not sql_raw:
        sql_raw = generate_sql(question)
        log.warning("Using fallback SQL")

    sql_clean: Optional[str] = None
    columns: Optional[list[str]] = None
    rows: Optional[list[list[Any]]] = None
    chart: Optional[ChartPayload] = None
    chart_type: Optional[str] = None

    # ── Step 3: Validate SQL ─────────────────────────────────────────────
    try:
        sql_clean = validate_sql(sql_raw)
    except SQLValidationError as exc:
        return JSONResponse(
            status_code=200,
            content=ChatResponse(
                message=f"SQL rejected: {exc}",
                sql_query=sql_raw,
            ).dict(),
        )

    # ── Step 4: Execute SQL ──────────────────────────────────────────────
    try:
        columns, rows = await async_run_sql(sql_clean)
    except Exception as exc:
        return JSONResponse(
            status_code=200,
            content=ChatResponse(
                message=f"SQL execution failed: {exc}",
                sql_query=sql_clean,
            ).dict(),
        )

    # ── Step 5: Message ──────────────────────────────────────────────────
    if rows:
        message = f"Here are the results for: {question}"
    else:
        message = "No data found for your query."

    # ── Step 6: Chart ────────────────────────────────────────────────────
    chart_data, chart_type = await async_build_chart(columns or [], rows or [])
    if chart_data:
        chart = ChartPayload(**chart_data)

    # ── Final response ───────────────────────────────────────────────────
    response = ChatResponse(
        message=message,
        sql_query=sql_clean,
        columns=columns,
        rows=rows,
        row_count=len(rows) if rows else 0,
        chart=chart,
        chart_type=chart_type,
        cached=False,
    )

    # ── Cache ────────────────────────────────────────────────────────────
    async with _cache_lock:
        _cache[question] = response.dict()

    return response


# ──────────────────────────────────────────────────────────────────────────
# GET /health
# ──────────────────────────────────────────────────────────────────────────

@app.get("/health", summary="Health check — DB status + agent memory count")
async def health() -> dict:
    # Both operations run concurrently via asyncio.gather
    db_status, memory_count = await asyncio.gather(
        async_db_health(),
        asyncio.to_thread(lambda: len(_agent_memory.list()) if _agent_memory else 0),
    )
    return {
        "status":              "ok",
        "database":            db_status,
        "agent_memory_items":  memory_count,
        "timestamp":           datetime.utcnow().isoformat() + "Z",
    }


# ──────────────────────────────────────────────────────────────────────────
# Global error handler
# ──────────────────────────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_error_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again."},
    )
